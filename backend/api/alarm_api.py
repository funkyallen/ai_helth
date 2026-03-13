from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from backend.dependencies import get_alarm_service
from backend.models.alarm_model import AlarmRecord


router = APIRouter(prefix="/alarms", tags=["alarms"])


@router.get("", response_model=list[AlarmRecord])
async def list_alarms(
    device_mac: str | None = Query(default=None),
    active_only: bool = Query(default=False),
) -> list[AlarmRecord]:
    return get_alarm_service().list_alarms(device_mac=device_mac, active_only=active_only)


@router.post("/{alarm_id}/acknowledge", response_model=AlarmRecord)
async def acknowledge_alarm(alarm_id: str) -> AlarmRecord:
    alarm = get_alarm_service().acknowledge(alarm_id)
    if not alarm:
        raise HTTPException(status_code=404, detail="Alarm not found")
    return alarm
