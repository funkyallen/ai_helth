from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


class DeviceStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    WARNING = "warning"


class DeviceRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    mac_address: str
    device_name: str = "T10-WATCH"
    user_id: str | None = None
    status: DeviceStatus = DeviceStatus.ONLINE
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("mac_address")
    @classmethod
    def normalize_mac(cls, value: str) -> str:
        return value.upper()


class DeviceRegisterRequest(BaseModel):
    mac_address: str
    device_name: str = "T10-WATCH"
    user_id: str | None = None
