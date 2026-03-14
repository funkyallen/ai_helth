from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.dependencies import get_agent_service, get_stream_service
from backend.models.user_model import UserRole


router = APIRouter(prefix="/chat", tags=["chat"])


class DeviceAnalysisRequest(BaseModel):
    device_mac: str
    question: str = Field(default="请结合最近一段时间的监测数据，给出完整分析。", min_length=4)
    role: UserRole = UserRole.FAMILY
    mode: str = Field(default="auto", pattern="^(auto|local|cloud)$")
    history_limit: int = Field(default=120, ge=12, le=1000)
    history_minutes: int = Field(default=1440, ge=30, le=43200)


class CommunityAnalysisRequest(BaseModel):
    question: str = Field(default="请对社区内多台监测设备最近一段时间的数据做汇总分析。", min_length=4)
    role: UserRole = UserRole.COMMUNITY
    mode: str = Field(default="auto", pattern="^(auto|local|cloud)$")
    history_minutes: int = Field(default=1440, ge=30, le=43200)
    per_device_limit: int = Field(default=240, ge=12, le=1000)
    device_macs: list[str] = Field(default_factory=list)


@router.post("/analyze")
async def analyze_health(payload: DeviceAnalysisRequest) -> dict[str, object]:
    recent = get_stream_service().recent_in_window(
        payload.device_mac,
        minutes=payload.history_minutes,
        limit=payload.history_limit,
    )
    return get_agent_service().analyze_device(
        role=payload.role,
        question=payload.question,
        samples=recent,
        mode=payload.mode,
    )


@router.post("/analyze/device")
async def analyze_device(payload: DeviceAnalysisRequest) -> dict[str, object]:
    return await analyze_health(payload)


@router.post("/analyze/community")
async def analyze_community(payload: CommunityAnalysisRequest) -> dict[str, object]:
    histories = get_stream_service().recent_by_devices(
        payload.device_macs or None,
        minutes=payload.history_minutes,
        per_device_limit=payload.per_device_limit,
    )
    return get_agent_service().analyze_community(
        role=payload.role,
        question=payload.question,
        device_samples=histories,
        mode=payload.mode,
    )
