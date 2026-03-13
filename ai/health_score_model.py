from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from statistics import mean

from backend.models.health_model import HealthSample


@dataclass(slots=True)
class PersonalBaseline:
    heart_rate: float
    temperature: float
    blood_oxygen: float
    systolic: float
    diastolic: float


class BaselineTracker:
    """Maintains a rolling personal baseline for each elder device."""

    def __init__(self, max_samples: int = 180) -> None:
        self._history: dict[str, deque[HealthSample]] = defaultdict(lambda: deque(maxlen=max_samples))

    def observe(self, sample: HealthSample) -> PersonalBaseline:
        history = self._history[sample.device_mac]
        history.append(sample)
        systolic_values = [entry.blood_pressure_pair[0] for entry in history]
        diastolic_values = [entry.blood_pressure_pair[1] for entry in history]
        return PersonalBaseline(
            heart_rate=mean(entry.heart_rate for entry in history),
            temperature=mean(entry.temperature for entry in history),
            blood_oxygen=mean(entry.blood_oxygen for entry in history),
            systolic=mean(systolic_values),
            diastolic=mean(diastolic_values),
        )


class HealthScoreService:
    """Simple explainable 0-100 scoring model for demo and competition defense."""

    def __init__(self, floor: int = 35) -> None:
        self._floor = floor

    def score(self, sample: HealthSample, baseline: PersonalBaseline) -> int:
        systolic, diastolic = sample.blood_pressure_pair
        penalty = 0.0
        penalty += min(abs(sample.heart_rate - baseline.heart_rate) * 0.35, 18)
        penalty += min(abs(sample.temperature - baseline.temperature) * 18, 20)
        penalty += min(abs(sample.blood_oxygen - baseline.blood_oxygen) * 2.6, 24)
        penalty += min(abs(systolic - baseline.systolic) * 0.22, 12)
        penalty += min(abs(diastolic - baseline.diastolic) * 0.25, 10)
        penalty += (100 - sample.battery) * 0.03
        if sample.sos_flag:
            penalty += 35
        return max(self._floor, min(100, round(100 - penalty)))
