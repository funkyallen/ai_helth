from __future__ import annotations

import json
import os
import time
from typing import Any, TypedDict
from urllib import error, request

from agent.analysis_service import HealthDataAnalysisService
from agent.langchain_rag_service import LangChainRAGService
from agent.prompting import build_prompt_package
from backend.config import Settings
from backend.models.health_model import HealthSample
from backend.models.user_model import UserRole

try:
    from langchain_core.prompts import ChatPromptTemplate
except Exception:
    ChatPromptTemplate = None

try:
    from langgraph.graph import END, START, StateGraph

    _LANGGRAPH_AVAILABLE = True
except Exception:
    END = None
    START = None
    StateGraph = None
    _LANGGRAPH_AVAILABLE = False

try:
    from langchain_qwq import ChatQwen
except Exception:
    ChatQwen = None

try:
    from langchain_openai import ChatOpenAI
except Exception:
    ChatOpenAI = None

try:
    from langchain_ollama import ChatOllama
except Exception:
    ChatOllama = None


class AgentState(TypedDict, total=False):
    scope: str
    role: UserRole
    question: str
    samples: list[HealthSample]
    community_samples: dict[str, list[HealthSample]]
    route_mode: str
    network_online: bool
    selected_mode: str
    analysis_payload: dict[str, Any]
    analysis_context: str
    retrieval_query: str
    knowledge_hits: list[str]
    prompt_text: str
    messages: list[Any]
    answer: str


class HealthAgentService:
    """LangGraph health agent with DashScope cloud routing and Ollama offline fallback."""

    def __init__(
        self,
        settings: Settings,
        rag_service: LangChainRAGService,
        analysis_service: HealthDataAnalysisService | None = None,
    ) -> None:
        self._settings = settings
        self._rag = rag_service
        self._analysis = analysis_service or HealthDataAnalysisService()
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
    ) -> dict[str, object]:
        return self.analyze_device(role=role, question=question, samples=samples, mode=mode)

    def analyze_device(
        self,
        *,
        role: UserRole,
        question: str,
        samples: list[HealthSample],
        mode: str = "auto",
    ) -> dict[str, object]:
        result = self._execute_graph(
            {
                "scope": "device",
                "role": role,
                "question": question,
                "samples": samples,
                "route_mode": mode,
            }
        )
        return self._format_result(result)

    def analyze_community(
        self,
        *,
        role: UserRole,
        question: str,
        device_samples: dict[str, list[HealthSample]],
        mode: str = "auto",
    ) -> dict[str, object]:
        result = self._execute_graph(
            {
                "scope": "community",
                "role": role,
                "question": question,
                "community_samples": device_samples,
                "route_mode": mode,
            }
        )
        return self._format_result(result)

    def _execute_graph(self, initial_state: AgentState) -> AgentState:
        if self._graph is not None:
            return self._graph.invoke(initial_state)

        state: AgentState = dict(initial_state)
        state.update(self._route_node(state))
        state.update(self._analysis_node(state))
        state.update(self._retrieve_node(state))
        state.update(self._prompt_node(state))
        state.update(self._generate_node(state))
        return state

    def _build_graph(self):
        graph = StateGraph(AgentState)
        graph.add_node("route", self._route_node)
        graph.add_node("analyze", self._analysis_node)
        graph.add_node("retrieve", self._retrieve_node)
        graph.add_node("prompt", self._prompt_node)
        graph.add_node("generate", self._generate_node)
        graph.add_edge(START, "route")
        graph.add_edge("route", "analyze")
        graph.add_edge("analyze", "retrieve")
        graph.add_edge("retrieve", "prompt")
        graph.add_edge("prompt", "generate")
        graph.add_edge("generate", END)
        return graph.compile()

    def _route_node(self, state: AgentState) -> AgentState:
        network_online = self._network_available()
        requested = str(state.get("route_mode", "auto")).lower()
        if requested not in {"auto", "local", "cloud"}:
            requested = "auto"

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

    def _analysis_node(self, state: AgentState) -> AgentState:
        scope = str(state.get("scope", "device"))
        question = str(state.get("question", "")).strip()
        if scope == "community":
            payload = self._analysis.summarize_community_history(
                dict(state.get("community_samples", {}))
            )
        else:
            payload = self._analysis.summarize_device(list(state.get("samples", [])))

        return {
            "analysis_payload": payload,
            "analysis_context": json.dumps(payload, ensure_ascii=False, indent=2, default=str),
            "retrieval_query": self._build_retrieval_query(scope=scope, question=question, analysis_payload=payload),
        }

    def _retrieve_node(self, state: AgentState) -> AgentState:
        query = str(state.get("retrieval_query") or state.get("question", "")).strip()
        if not query:
            return {"knowledge_hits": []}

        network_online = bool(state.get("network_online", False))
        hits = self._rag.search(
            query,
            top_k=self._settings.rag_top_k,
            network_online=network_online,
            allow_rerank=network_online and self._settings.qwen_enable_rerank,
        )
        return {"knowledge_hits": hits}

    def _prompt_node(self, state: AgentState) -> AgentState:
        package = build_prompt_package(
            role=state.get("role", UserRole.FAMILY),
            scope=str(state.get("scope", "device")),
            question=str(state.get("question", "")),
            analysis_context=str(state.get("analysis_context", "{}")),
            knowledge_context="\n\n".join(state.get("knowledge_hits", [])),
        )
        system_text = package["system"]
        user_text = package["user"]
        prompt_text = f"{system_text}\n\n{user_text}".strip()
        messages: list[Any] = []
        if ChatPromptTemplate is not None:
            try:
                prompt = ChatPromptTemplate.from_messages(
                    [("system", system_text), ("human", user_text)]
                )
                messages = prompt.format_messages()
            except Exception:
                messages = []
        return {
            "prompt_text": prompt_text,
            "messages": messages,
        }

    def _generate_node(self, state: AgentState) -> AgentState:
        prompt_text = str(state.get("prompt_text", "")).strip()
        messages = list(state.get("messages", []))
        selected_mode = str(state.get("selected_mode", "local"))
        scope = str(state.get("scope", "device"))
        if not prompt_text:
            return {"answer": self._fallback_answer(state.get("analysis_payload", {}), scope), "selected_mode": selected_mode}

        if selected_mode == "cloud":
            answer = self._invoke_cloud(prompt_text, messages)
            if answer:
                return {"answer": answer, "selected_mode": "cloud"}
            local_answer = self._invoke_local(prompt_text, messages)
            return {
                "answer": local_answer or self._fallback_answer(state.get("analysis_payload", {}), scope),
                "selected_mode": "local",
            }

        answer = self._invoke_local(prompt_text, messages)
        if answer:
            return {"answer": answer, "selected_mode": "local"}

        cloud_answer = self._invoke_cloud(prompt_text, messages)
        if cloud_answer:
            return {"answer": cloud_answer, "selected_mode": "cloud"}

        return {"answer": self._fallback_answer(state.get("analysis_payload", {}), scope), "selected_mode": selected_mode}

    def _invoke_local(self, prompt_text: str, messages: list[Any]) -> str | None:
        if ChatOllama is not None:
            if self._local_llm is None:
                self._local_llm = self._build_local_llm()
            if self._local_llm is not None:
                try:
                    response = self._local_llm.invoke(messages or prompt_text)
                    answer = self._extract_message_text(response)
                    if answer:
                        return answer
                except Exception:
                    pass
        return self._call_ollama_http(prompt_text)

    def _invoke_cloud(self, prompt_text: str, messages: list[Any]) -> str | None:
        if not self._settings.qwen_api_key:
            return None

        if self._cloud_llm is None:
            self._cloud_llm = self._build_cloud_llm()
        if self._cloud_llm is not None:
            try:
                response = self._cloud_llm.invoke(messages or prompt_text)
                answer = self._extract_message_text(response)
                if answer:
                    return answer
            except Exception:
                pass
        return self._call_qwen_http(prompt_text)

    def _build_local_llm(self):
        if ChatOllama is None:
            return None
        try:
            return ChatOllama(
                model=self._settings.ollama_model,
                base_url=self._settings.ollama_base_url,
                temperature=0.2,
            )
        except Exception:
            return None

    def _build_cloud_llm(self):
        if not self._settings.qwen_api_key:
            return None

        if ChatQwen is not None:
            os.environ["DASHSCOPE_API_KEY"] = self._settings.qwen_api_key
            try:
                return ChatQwen(
                    model=self._settings.qwen_model,
                    temperature=0.2,
                    timeout=self._settings.llm_timeout_seconds,
                )
            except TypeError:
                try:
                    return ChatQwen(
                        model=self._settings.qwen_model,
                        temperature=0.2,
                        request_timeout=self._settings.llm_timeout_seconds,
                    )
                except Exception:
                    pass
            except Exception:
                pass

        if ChatOpenAI is None:
            return None

        try:
            return ChatOpenAI(
                model=self._settings.qwen_model,
                api_key=self._settings.qwen_api_key,
                base_url=self._settings.qwen_api_base,
                timeout=self._settings.llm_timeout_seconds,
                temperature=0.2,
            )
        except TypeError:
            try:
                return ChatOpenAI(
                    model=self._settings.qwen_model,
                    api_key=self._settings.qwen_api_key,
                    base_url=self._settings.qwen_api_base,
                    request_timeout=self._settings.llm_timeout_seconds,
                    temperature=0.2,
                )
            except Exception:
                return None
        except Exception:
            return None

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

    def _call_ollama_http(self, prompt_text: str) -> str | None:
        url = f"{self._settings.ollama_base_url.rstrip('/')}/api/chat"
        payload = json.dumps(
            {
                "model": self._settings.ollama_model,
                "stream": False,
                "messages": [{"role": "user", "content": prompt_text}],
            },
            ensure_ascii=False,
        ).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        return self._post_json(
            url,
            payload,
            headers,
            parser=lambda body: body.get("message", {}).get("content"),
        )

    def _call_qwen_http(self, prompt_text: str) -> str | None:
        url = f"{self._settings.qwen_api_base.rstrip('/')}/chat/completions"
        payload = json.dumps(
            {
                "model": self._settings.qwen_model,
                "messages": [{"role": "user", "content": prompt_text}],
                "temperature": 0.2,
            },
            ensure_ascii=False,
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

    def _build_retrieval_query(self, *, scope: str, question: str, analysis_payload: dict[str, Any]) -> str:
        if scope == "community":
            distribution = analysis_payload.get("risk_distribution", {})
            priority_devices = analysis_payload.get("priority_devices", [])
            focus_terms = []
            if isinstance(priority_devices, list):
                for item in priority_devices[:3]:
                    if not isinstance(item, dict):
                        continue
                    flags = item.get("risk_flags", [])
                    joined_flags = " ".join(str(flag) for flag in flags)
                    focus_terms.append(f"{item.get('device_mac', '')} {joined_flags}".strip())
            return " ".join(
                part
                for part in [
                    question or "社区多设备健康汇总分析",
                    "社区养老 多设备 风险分层 随访",
                    f"high={distribution.get('high', 0)}",
                    f"medium={distribution.get('medium', 0)}",
                    *focus_terms,
                ]
                if part
            )

        risk_flags = analysis_payload.get("risk_flags", [])
        notable_events = analysis_payload.get("notable_events", [])
        return " ".join(
            part
            for part in [
                question or "请分析最近监测数据",
                "老人 健康监测 趋势 风险 建议",
                *(str(flag) for flag in risk_flags[:4]),
                *(str(event) for event in notable_events[:2]),
            ]
            if part
        )

    def _format_result(self, result: AgentState) -> dict[str, object]:
        answer = str(result.get("answer", "")).strip()
        scope = str(result.get("scope", "device"))
        if not answer:
            answer = self._fallback_answer(result.get("analysis_payload", {}), scope)
        return {
            "scope": scope,
            "mode": str(result.get("selected_mode", "local")),
            "network_online": bool(result.get("network_online", False)),
            "answer": answer,
            "references": list(result.get("knowledge_hits", [])),
            "analysis": dict(result.get("analysis_payload", {})),
        }

    def _fallback_answer(self, analysis_payload: dict[str, Any], scope: str) -> str:
        if scope == "community":
            device_count = int(analysis_payload.get("device_count", 0))
            distribution = analysis_payload.get("risk_distribution", {})
            priority_devices = analysis_payload.get("priority_devices", [])
            recommendations = analysis_payload.get("recommendations", [])
            focus = "、".join(
                str(item.get("device_mac"))
                for item in priority_devices[:3]
                if isinstance(item, dict) and item.get("device_mac")
            )
            return (
                f"本次社区汇总覆盖 {device_count} 台设备，"
                f"其中高风险 {distribution.get('high', 0)} 台、中风险 {distribution.get('medium', 0)} 台、低风险 {distribution.get('low', 0)} 台。"
                f"优先关注：{focus or '当前暂无明确重点对象'}。"
                f"建议：{'；'.join(str(item) for item in recommendations[:3]) or '继续保持常规巡检。'}"
            )

        latest = analysis_payload.get("latest", {})
        risk_level = self._risk_label(str(analysis_payload.get("risk_level", "unknown")))
        window = analysis_payload.get("window", {})
        notable_events = analysis_payload.get("notable_events", [])
        recommendations = analysis_payload.get("recommendations", [])
        return (
            f"当前综合风险等级为{risk_level}。"
            f"最近监测窗口约 {window.get('duration_minutes', 0)} 分钟，"
            f"最新指标为心率 {latest.get('heart_rate', '--')} bpm、"
            f"体温 {latest.get('temperature', '--')}℃、"
            f"血氧 {latest.get('blood_oxygen', '--')}%、"
            f"血压 {latest.get('blood_pressure', '--')}。"
            f"重点情况：{notable_events[0] if notable_events else '暂无明显异常事件。'}"
            f"建议：{'；'.join(str(item) for item in recommendations[:3]) or '继续监测。'}"
        )

    @staticmethod
    def _risk_label(level: str) -> str:
        return {
            "low": "低",
            "medium": "中",
            "high": "高",
            "unknown": "未知",
        }.get(level, level)

    @staticmethod
    def _extract_message_text(message: Any) -> str | None:
        content = getattr(message, "content", None)
        if isinstance(content, str):
            value = content.strip()
            return value or None
        if isinstance(content, list):
            parts: list[str] = []
            for row in content:
                if isinstance(row, str) and row.strip():
                    parts.append(row.strip())
                elif isinstance(row, dict):
                    text = row.get("text") or row.get("content")
                    if isinstance(text, str) and text.strip():
                        parts.append(text.strip())
            if parts:
                return "\n".join(parts)
        if isinstance(message, str):
            value = message.strip()
            return value or None
        return None
