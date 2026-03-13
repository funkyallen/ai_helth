from __future__ import annotations

from pydantic import BaseModel, Field
from fastapi import APIRouter

from backend.dependencies import get_agent_service, get_stream_service
from backend.models.user_model import UserRole


router = APIRouter(prefix="/chat", tags=["chat"])


class ChatAnalysisRequest(BaseModel):
    device_mac: str
    question: str = Field(min_length=4)
    role: UserRole = UserRole.FAMILY
    mode: str = Field(default="local", pattern="^(local|cloud)$")
    history_limit: int = Field(default=36, ge=12, le=500)


@router.post("/analyze")
async def analyze_health(payload: ChatAnalysisRequest) -> dict[str, object]:
    recent = get_stream_service().recent(payload.device_mac, limit=payload.history_limit)
    return get_agent_service().analyze(
        role=payload.role,
        question=payload.question,
        samples=recent,
        mode=payload.mode,
    )
