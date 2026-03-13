from __future__ import annotations

from backend.models.alarm_model import AlarmRecord
from backend.models.health_model import HealthSample


class AlarmService:
    """Evaluates incoming samples and stores active alarms."""

    def __init__(self, detector: object) -> None:
        self._detector = detector
        self._alarms: list[AlarmRecord] = []

    def evaluate(self, sample: HealthSample) -> list[AlarmRecord]:
        alarms = self._detector.evaluate(sample)
        if alarms:
            self._alarms.extend(alarms)
        self._alarms.sort(key=lambda item: (item.alarm_level.value, item.created_at), reverse=False)
        return alarms

    def list_alarms(self, device_mac: str | None = None, active_only: bool = False) -> list[AlarmRecord]:
        alarms = self._alarms
        if device_mac:
            alarms = [alarm for alarm in alarms if alarm.device_mac == device_mac.upper()]
        if active_only:
            alarms = [alarm for alarm in alarms if not alarm.acknowledged]
        return alarms

    def acknowledge(self, alarm_id: str) -> AlarmRecord | None:
        for index, alarm in enumerate(self._alarms):
            if alarm.id == alarm_id:
                updated = alarm.model_copy(update={"acknowledged": True})
                self._alarms[index] = updated
                return updated
        return None
