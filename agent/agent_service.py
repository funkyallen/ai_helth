from __future__ import annotations

import json
import time
from statistics import mean
from typing import Any, TypedDict
from urllib import error, request

from agent.prompt_templates import build_prompt
from agent.rag_service import RAGService
from backend.config import Settings
from backend.models.health_model import HealthSample
from backend.models.user_model import UserRole

try:
    from langchain_community.chat_models import ChatOllama
    from langchain_core.messages import HumanMessage
    from langgraph.graph import END, START, StateGraph

    _LANGGRAPH_AVAILABLE = True
except Exception:  # pragma: no cover - optional runtime dependency
    ChatOllama = None
    HumanMessage = None
    END = None
    START = None
    StateGraph = None
    _LANGGRAPH_AVAILABLE = False

try:
    from langchain_community.chat_models import ChatOpenAI
except Exception:  # pragma: no cover - optional runtime dependency
    ChatOpenAI = None


class AgentState(TypedDict, total=False):
    role: UserRole
    question: str
    samples: list[HealthSample]
    route_mode: str
    network_online: bool
    selected_mode: str
    health_context: str
    knowledge_hits: list[str]
    prompt: str
    answer: str


class HealthAgentService:
    """LangGraph-based health agent with Qwen cloud + Ollama local routing."""

    def __init__(self, settings: Settings, rag_service: RAGService) -> None:
        self._settings = settings
        self._rag = rag_service
        self._cloud_llm = None
        self._local_llm = None
        self._network_cache_at = 0.0
        self._network_cache_value = False
        self._graph = self._build_graph() if _LANGGRAPH_AVAILABLE else None

    def analyze(
        self,
        *,
        role: UserRole,
        question: str,
        samples: list[HealthSample],
        mode: str = "auto",
    ) -> dict[str, str | bool | list[str]]:
        route_mode = mode if mode in {"auto", "local", "cloud"} else "auto"
        initial_state: AgentState = {
            "role": role,
            "question": question,
            "samples": samples,
            "route_mode": route_mode,
        }

        if self._graph is not None:
            result = self._graph.invoke(initial_state)
        else:
            result = self._run_fallback_pipeline(initial_state)

        answer = str(result.get("answer", "")).strip()
        selected_mode = str(result.get("selected_mode", "local"))
        knowledge_hits = list(result.get("knowledge_hits", []))
        network_online = bool(result.get("network_online", False))

        if not answer:
            answer = self._fallback_answer(samples, role)

        return {
            "mode": selected_mode,
            "network_online": network_online,
            "answer": answer,
            "references": knowledge_hits,
        }

    def _build_graph(self):
        graph = StateGraph(AgentState)
        graph.add_node("route", self._route_node)
        graph.add_node("retrieve", self._retrieve_node)
        graph.add_node("prompt", self._prompt_node)
        graph.add_node("generate", self._llm_node)

        graph.add_edge(START, "route")
        graph.add_edge("route", "retrieve")
        graph.add_edge("retrieve", "prompt")
        graph.add_edge("prompt", "generate")
        graph.add_edge("generate", END)
        return graph.compile()

    def _run_fallback_pipeline(self, initial_state: AgentState) -> AgentState:
        state: AgentState = dict(initial_state)
        state.update(self._route_node(state))
        state.update(self._retrieve_node(state))
        state.update(self._prompt_node(state))
        state.update(self._llm_node(state))
        return state

    def _route_node(self, state: AgentState) -> AgentState:
        network_online = self._network_available()
        requested = str(state.get("route_mode", "auto"))

        if requested == "local":
            selected_mode = "local"
        elif requested == "cloud":
            selected_mode = "cloud" if network_online and bool(self._settings.qwen_api_key) else "local"
        else:
            selected_mode = "cloud" if network_online and bool(self._settings.qwen_api_key) else "local"

        return {
            "network_online": network_online,
            "selected_mode": selected_mode,
        }

    def _retrieve_node(self, state: AgentState) -> AgentState:
        question = str(state.get("question", ""))
        network_online = bool(state.get("network_online", False))
        hits = self._rag.search(
            question,
            top_k=self._settings.rag_top_k,
            network_online=network_online,
            allow_rerank=network_online and self._settings.qwen_enable_rerank,
        )
        return {"knowledge_hits": hits}

    def _prompt_node(self, state: AgentState) -> AgentState:
        role = state.get("role", UserRole.FAMILY)
        question = str(state.get("question", ""))
        samples = list(state.get("samples", []))
        health_context = self._build_health_context(samples)
        knowledge_context = "\n\n".join(state.get("knowledge_hits", []))
        prompt = build_prompt(role, question, health_context, knowledge_context)
        return {
            "health_context": health_context,
            "prompt": prompt,
        }

    def _llm_node(self, state: AgentState) -> AgentState:
        prompt = str(state.get("prompt", "")).strip()
        selected_mode = str(state.get("selected_mode", "local"))
        if not prompt:
            return {"answer": "", "selected_mode": selected_mode}

        if selected_mode == "cloud":
            answer = self._invoke_cloud(prompt)
            if answer:
                return {"answer": answer, "selected_mode": "cloud"}
            local_answer = self._invoke_local(prompt)
            return {"answer": local_answer or "", "selected_mode": "local"}

        answer = self._invoke_local(prompt)
        if answer:
            return {"answer": answer, "selected_mode": "local"}

        cloud_answer = self._invoke_cloud(prompt)
        if cloud_answer:
            return {"answer": cloud_answer, "selected_mode": "cloud"}

        return {"answer": "", "selected_mode": "local"}

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

    def _network_available(self) -> bool:
        ttl = max(5, self._settings.network_probe_cache_seconds)
        now = time.monotonic()
        if now - self._network_cache_at < ttl:
            return self._network_cache_value

        probe_url = self._settings.network_probe_url.strip() or self._settings.qwen_api_base
        req = request.Request(url=probe_url, method="HEAD")
        try:
            with request.urlopen(req, timeout=self._settings.network_probe_timeout_seconds) as response:
                status = int(getattr(response, "status", 200))
                online = status < 500
        except error.HTTPError as exc:
            online = exc.code < 500
        except (error.URLError, TimeoutError):
            online = False

        self._network_cache_at = now
        self._network_cache_value = online
        return online

    def _invoke_local(self, prompt: str) -> str | None:
        if ChatOllama is not None and HumanMessage is not None:
            if self._local_llm is None:
                self._local_llm = self._build_local_llm()
            if self._local_llm is not None:
                try:
                    response = self._local_llm.invoke([HumanMessage(content=prompt)])
                    answer = self._extract_message_text(response)
                    if answer:
                        return answer
                except Exception:
                    pass
        return self._call_ollama_http(prompt)

    def _invoke_cloud(self, prompt: str) -> str | None:
        if not self._settings.qwen_api_key:
            return None

        if ChatOpenAI is not None and HumanMessage is not None:
            if self._cloud_llm is None:
                self._cloud_llm = self._build_cloud_llm()
            if self._cloud_llm is not None:
                try:
                    response = self._cloud_llm.invoke([HumanMessage(content=prompt)])
                    answer = self._extract_message_text(response)
                    if answer:
                        return answer
                except Exception:
                    pass

        return self._call_qwen_http(prompt)

    def _build_local_llm(self):
        try:
            return ChatOllama(
                model=self._settings.ollama_model,
                base_url=self._settings.ollama_base_url,
                temperature=0.2,
            )
        except TypeError:
            return ChatOllama(model=self._settings.ollama_model, temperature=0.2)
        except Exception:
            return None

    def _build_cloud_llm(self):
        if ChatOpenAI is None:
            return None

        try:
            return ChatOpenAI(
                model_name=self._settings.qwen_model,
                openai_api_base=self._settings.qwen_api_base,
                openai_api_key=self._settings.qwen_api_key,
                temperature=0.3,
                request_timeout=self._settings.llm_timeout_seconds,
            )
        except TypeError:
            try:
                return ChatOpenAI(
                    model=self._settings.qwen_model,
                    base_url=self._settings.qwen_api_base,
                    api_key=self._settings.qwen_api_key,
                    temperature=0.3,
                    timeout=self._settings.llm_timeout_seconds,
                )
            except Exception:
                return None
        except Exception:
            return None

    def _call_ollama_http(self, prompt: str) -> str | None:
        url = f"{self._settings.ollama_base_url}/api/chat"
        payload = json.dumps(
            {
                "model": self._settings.ollama_model,
                "stream": False,
                "messages": [{"role": "user", "content": prompt}],
            }
        ).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        return self._post_json(
            url,
            payload,
            headers,
            parser=lambda body: body.get("message", {}).get("content"),
        )

    def _call_qwen_http(self, prompt: str) -> str | None:
        url = f"{self._settings.qwen_api_base.rstrip('/')}/chat/completions"
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
                parsed = parser(body)
                return str(parsed).strip() if parsed else None
        except (error.URLError, error.HTTPError, TimeoutError, json.JSONDecodeError):
            return None

    @staticmethod
    def _extract_message_text(message: Any) -> str | None:
        content = getattr(message, "content", None)
        if isinstance(content, str):
            value = content.strip()
            return value or None
        if isinstance(content, list):
            parts: list[str] = []
            for row in content:
                if isinstance(row, str):
                    if row.strip():
                        parts.append(row.strip())
                elif isinstance(row, dict):
                    text = row.get("text") or row.get("content")
                    if isinstance(text, str) and text.strip():
                        parts.append(text.strip())
            if parts:
                return "\n".join(parts)
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
