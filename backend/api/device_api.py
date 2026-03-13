from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.dependencies import get_device_service
from backend.models.device_model import DeviceRecord, DeviceRegisterRequest


router = APIRouter(prefix="/devices", tags=["devices"])


@router.get("", response_model=list[DeviceRecord])
async def list_devices() -> list[DeviceRecord]:
    return get_device_service().list_devices()


@router.get("/{mac_address}", response_model=DeviceRecord)
async def get_device(mac_address: str) -> DeviceRecord:
    device = get_device_service().get_device(mac_address)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device


@router.post("/register", response_model=DeviceRecord)
async def register_device(payload: DeviceRegisterRequest) -> DeviceRecord:
    return get_device_service().register_device(payload)
