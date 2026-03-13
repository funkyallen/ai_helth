from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

from backend.models.health_model import HealthSample, HealthTrendPoint


class StreamService:
    """Stores recent realtime samples and trend-ready history in memory."""

    def __init__(self, retention_points: int = 600) -> None:
        self._retention_points = retention_points
        self._streams: dict[str, deque[HealthSample]] = defaultdict(
            lambda: deque(maxlen=self._retention_points)
        )

    def publish(self, sample: HealthSample) -> None:
        self._streams[sample.device_mac].append(sample)

    def latest(self, device_mac: str) -> HealthSample | None:
        stream = self._streams.get(device_mac.upper())
        if not stream:
            return None
        return stream[-1]

    def recent(self, device_mac: str, limit: int = 60) -> list[HealthSample]:
        stream = self._streams.get(device_mac.upper(), deque())
        return list(stream)[-limit:]

    def trend(
        self,
        device_mac: str,
        *,
        minutes: int = 60,
        limit: int = 120,
    ) -> list[HealthTrendPoint]:
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(minutes=minutes)
        values = [
            HealthTrendPoint(
                timestamp=sample.timestamp,
                heart_rate=sample.heart_rate,
                temperature=sample.temperature,
                blood_oxygen=sample.blood_oxygen,
                health_score=sample.health_score,
            )
            for sample in self._streams.get(device_mac.upper(), deque())
            if sample.timestamp >= cutoff
        ]
        return values[-limit:]

    def latest_samples(self) -> list[HealthSample]:
        snapshots: list[HealthSample] = []
        for stream in self._streams.values():
            if stream:
                snapshots.append(stream[-1])
        return snapshots
