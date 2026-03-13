from __future__ import annotations

import json
from statistics import mean
from urllib import error, request

from agent.prompt_templates import build_prompt
from agent.rag_service import RAGService
from backend.config import Settings
from backend.models.health_model import HealthSample
from backend.models.user_model import UserRole


class HealthAgentService:
    """Unified agent entry for Qwen cloud mode and Ollama local mode."""

    def __init__(self, settings: Settings, rag_service: RAGService) -> None:
        self._settings = settings
        self._rag = rag_service

    def analyze(
        self,
        *,
        role: UserRole,
        question: str,
        samples: list[HealthSample],
        mode: str = "local",
    ) -> dict[str, str | list[str]]:
        health_context = self._build_health_context(samples)
        knowledge_hits = self._rag.search(question, top_k=3)
        prompt = build_prompt(role, question, health_context, "\n\n".join(knowledge_hits))

        if mode == "cloud":
            answer = self._call_qwen(prompt)
        else:
            answer = self._call_ollama(prompt)

        if not answer:
            answer = self._fallback_answer(samples, role)

        return {
            "mode": mode,
            "answer": answer,
            "references": knowledge_hits,
        }

    @staticmethod
    def _build_health_context(samples: list[HealthSample]) -> str:
        if not samples:
            return "暂无最近 24 小时健康数据。"
        latest = samples[-1]
        avg_hr = round(mean(item.heart_rate for item in samples), 1)
        avg_temp = round(mean(item.temperature for item in samples), 1)
        avg_spo2 = round(mean(item.blood_oxygen for item in samples), 1)
        return (
            f"设备：{latest.device_mac}\n"
            f"最近样本数：{len(samples)}\n"
            f"当前心率：{latest.heart_rate} bpm\n"
            f"当前体温：{latest.temperature:.1f}℃\n"
            f"当前血氧：{latest.blood_oxygen}%\n"
            f"当前血压：{latest.blood_pressure} mmHg\n"
            f"当前健康分：{latest.health_score}\n"
            f"24小时均值：心率 {avg_hr} / 体温 {avg_temp} / 血氧 {avg_spo2}\n"
            f"SOS 状态：{'是' if latest.sos_flag else '否'}"
        )

    def _call_ollama(self, prompt: str) -> str | None:
        url = f"{self._settings.ollama_base_url}/api/chat"
        payload = json.dumps(
            {
                "model": self._settings.ollama_model,
                "stream": False,
                "messages": [{"role": "user", "content": prompt}],
            }
        ).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        return self._post_json(url, payload, headers, parser=lambda body: body.get("message", {}).get("content"))

    def _call_qwen(self, prompt: str) -> str | None:
        if not self._settings.qwen_api_key:
            return None
        url = f"{self._settings.qwen_api_base}/chat/completions"
        payload = json.dumps(
            {
                "model": self._settings.qwen_model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
            }
        ).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._settings.qwen_api_key}",
        }
        return self._post_json(
            url,
            payload,
            headers,
            parser=lambda body: body.get("choices", [{}])[0].get("message", {}).get("content"),
        )

    def _post_json(self, url: str, payload: bytes, headers: dict[str, str], parser) -> str | None:
        req = request.Request(url=url, data=payload, headers=headers, method="POST")
        try:
            with request.urlopen(req, timeout=self._settings.llm_timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
                return parser(body)
        except (error.URLError, error.HTTPError, TimeoutError, json.JSONDecodeError):
            return None

    @staticmethod
    def _fallback_answer(samples: list[HealthSample], role: UserRole) -> str:
        if not samples:
            return "当前没有足够的健康数据，建议先检查设备连接状态和采集链路。"

        latest = samples[-1]
        risk = "低"
        if latest.sos_flag or latest.blood_oxygen < 90 or latest.heart_rate > 180:
            risk = "高"
        elif latest.heart_rate > 110 or latest.temperature > 37.6:
            risk = "中"

        role_hint = {
            UserRole.FAMILY: "建议先联系老人，确认主诉和意识状态，并观察 10 分钟内指标变化。",
            UserRole.COMMUNITY: "建议社区值守人员优先复核高风险对象，并安排分级随访。",
            UserRole.ELDER: "建议先坐下休息，保持呼吸平稳，如不适持续请联系家人或医生。",
            UserRole.ADMIN: "建议核对设备在线状态、网关日志和最近一次告警处理记录。",
        }[role]
        return (
            f"当前综合风险等级为{risk}。"
            f"最新指标为心率 {latest.heart_rate}、体温 {latest.temperature:.1f}℃、"
            f"血氧 {latest.blood_oxygen}%、血压 {latest.blood_pressure}。{role_hint}"
        )
