from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


class AlarmType(str, Enum):
    SOS = "sos"
    VITAL_CRITICAL = "vital_critical"
    ZSCORE_WARNING = "zscore_warning"
    COMMUNITY_RISK = "community_risk"
    DEVICE_STATUS = "device_status"


class AlarmPriority(int, Enum):
    SOS = 1
    CRITICAL = 2
    WARNING = 3
    NOTICE = 4


class AlarmRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    device_mac: str
    alarm_type: AlarmType
    alarm_level: AlarmPriority
    message: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    acknowledged: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("device_mac")
    @classmethod
    def normalize_mac(cls, value: str) -> str:
        return value.upper()
