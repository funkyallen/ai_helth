from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    """Application settings aligned with the 2026 competition platform."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "AIoT智慧康养健康监测系统"
    environment: str = "development"
    api_v1_prefix: str = "/api/v1"
    debug: bool = True

    host: str = "0.0.0.0"
    port: int = 8000

    allowed_mac_prefixes: list[str] = Field(default_factory=lambda: ["53:57:08"])
    default_device_name: str = "T10-WATCH"
    device_uuid: str = "52616469-6F6C-616E-642D-541000000000"
    service_uuid: str = "00001803-494c-4f47-4943-544543480000"

    database_url: str = f"sqlite+aiosqlite:///{(BASE_DIR / 'data' / 'app.db').as_posix()}"
    redis_url: str = "redis://localhost:6379/0"
    chroma_path: str = str(BASE_DIR / "data" / "chroma")

    qwen_api_base: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    qwen_api_key: str = ""
    qwen_model: str = "qwen-plus"
    qwen_embedding_model: str = "text-embedding-v3"
    qwen_rerank_model: str = "qwen-reranker-v1"
    qwen_rerank_api: str = "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank"
    qwen_enable_rerank: bool = True

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:1.7b"

    llm_timeout_seconds: int = 10
    rag_timeout_seconds: int = 15
    rag_top_k: int = 3
    rag_fetch_k: int = 8
    rag_chunk_size: int = 700
    rag_chunk_overlap: int = 150

    network_probe_url: str = "https://dashscope.aliyuncs.com"
    network_probe_timeout_seconds: int = 3
    network_probe_cache_seconds: int = 20

    jwt_secret: str = "replace-me-in-production"
    ws_heartbeat_seconds: int = 30

    realtime_window_size: int = 30
    zscore_threshold: float = 2.4
    mock_device_count: int = 10
    mock_push_interval_seconds: float = 1.2
    use_mock_data: bool = True

    sos_broadcast_window_seconds: int = 15
    health_score_floor: int = 35
    stream_retention_points: int = 600

    @property
    def data_dir(self) -> Path:
        return BASE_DIR / "data"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
