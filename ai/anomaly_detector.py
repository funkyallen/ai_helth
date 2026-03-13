from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from statistics import mean, pstdev

from backend.models.alarm_model import AlarmPriority, AlarmRecord, AlarmType
from backend.models.health_model import HealthSample

try:
    import torch
    from torch import nn
except ImportError:
    torch = None
    nn = None

try:
    from sklearn.cluster import DBSCAN
except ImportError:
    DBSCAN = None


@dataclass(slots=True)
class FeatureWindow:
    heart_rates: deque[int]
    temperatures: deque[float]
    spo2_values: deque[int]


class RealtimeAnomalyDetector:
    """Competition-oriented realtime detector with rules + dynamic z-score."""

    def __init__(self, window_size: int = 30, zscore_threshold: float = 2.4) -> None:
        self._window_size = window_size
        self._zscore_threshold = zscore_threshold
        self._windows: dict[str, FeatureWindow] = defaultdict(
            lambda: FeatureWindow(
                heart_rates=deque(maxlen=self._window_size),
                temperatures=deque(maxlen=self._window_size),
                spo2_values=deque(maxlen=self._window_size),
            )
        )

    def evaluate(self, sample: HealthSample) -> list[AlarmRecord]:
        alarms: list[AlarmRecord] = []
        systolic, diastolic = sample.blood_pressure_pair

        if sample.sos_flag:
            alarms.append(
                AlarmRecord(
                    device_mac=sample.device_mac,
                    alarm_type=AlarmType.SOS,
                    alarm_level=AlarmPriority.SOS,
                    message="检测到手环 SOS 持续广播，请立即联系家属并安排现场核验。",
                    metadata={"event": "sos_hold_5s"},
                )
            )

        if sample.heart_rate > 180 or sample.heart_rate < 40:
            alarms.append(
                AlarmRecord(
                    device_mac=sample.device_mac,
                    alarm_type=AlarmType.VITAL_CRITICAL,
                    alarm_level=AlarmPriority.CRITICAL,
                    message=f"心率异常：{sample.heart_rate} bpm。",
                    metadata={"metric": "heart_rate", "value": sample.heart_rate},
                )
            )

        if sample.temperature > 38.5 or sample.temperature < 35.0:
            alarms.append(
                AlarmRecord(
                    device_mac=sample.device_mac,
                    alarm_type=AlarmType.VITAL_CRITICAL,
                    alarm_level=AlarmPriority.CRITICAL,
                    message=f"体温异常：{sample.temperature:.1f}℃。",
                    metadata={"metric": "temperature", "value": sample.temperature},
                )
            )

        if sample.blood_oxygen < 90:
            alarms.append(
                AlarmRecord(
                    device_mac=sample.device_mac,
                    alarm_type=AlarmType.VITAL_CRITICAL,
                    alarm_level=AlarmPriority.CRITICAL,
                    message=f"血氧偏低：{sample.blood_oxygen}%。",
                    metadata={"metric": "blood_oxygen", "value": sample.blood_oxygen},
                )
            )

        if systolic > 180 or diastolic > 120 or systolic < 90 or diastolic < 60:
            alarms.append(
                AlarmRecord(
                    device_mac=sample.device_mac,
                    alarm_type=AlarmType.VITAL_CRITICAL,
                    alarm_level=AlarmPriority.CRITICAL,
                    message=f"血压异常：{sample.blood_pressure} mmHg。",
                    metadata={
                        "metric": "blood_pressure",
                        "systolic": systolic,
                        "diastolic": diastolic,
                    },
                )
            )

        window = self._windows[sample.device_mac]
        self._append_window(window, sample)

        hr_z = self._safe_zscore(list(window.heart_rates), sample.heart_rate)
        temp_z = self._safe_zscore(list(window.temperatures), sample.temperature)
        spo2_z = self._safe_zscore(list(window.spo2_values), sample.blood_oxygen)
        sample.anomaly_score = round(max(hr_z, temp_z, spo2_z), 3)

        if sample.anomaly_score >= self._zscore_threshold and not alarms:
            alarms.append(
                AlarmRecord(
                    device_mac=sample.device_mac,
                    alarm_type=AlarmType.ZSCORE_WARNING,
                    alarm_level=AlarmPriority.WARNING,
                    message="实时动态 Z-Score 检测到生命体征漂移，建议持续观察。",
                    metadata={"zscore": sample.anomaly_score},
                )
            )

        return alarms

    @staticmethod
    def _append_window(window: FeatureWindow, sample: HealthSample) -> None:
        window.heart_rates.append(sample.heart_rate)
        window.temperatures.append(sample.temperature)
        window.spo2_values.append(sample.blood_oxygen)

    @staticmethod
    def _safe_zscore(values: list[float], current_value: float) -> float:
        if len(values) < 5:
            return 0.0
        sigma = pstdev(values)
        if sigma == 0:
            return 0.0
        return abs((current_value - mean(values)) / sigma)


class TinyTemporalAutoencoder(nn.Module if nn else object):
    """Small LSTM autoencoder used as a light replacement for LSTM-VAE in local demos."""

    def __init__(self, input_size: int = 4, hidden_size: int = 16) -> None:
        if not nn:
            return
        super().__init__()
        self.encoder = nn.LSTM(input_size=input_size, hidden_size=hidden_size, batch_first=True)
        self.decoder = nn.LSTM(input_size=hidden_size, hidden_size=input_size, batch_first=True)

    def forward(self, inputs):
        encoded, _ = self.encoder(inputs)
        reconstructed, _ = self.decoder(encoded)
        return reconstructed


class IntelligentAnomalyScorer:
    """Minutes-level intelligent scorer. Uses torch when available and falls back otherwise."""

    def __init__(self) -> None:
        self._model = TinyTemporalAutoencoder() if torch else None

    def score_sequence(self, windows: list[list[float]]) -> float:
        if not windows:
            return 0.0
        if torch and self._model:
            tensor = torch.tensor([windows], dtype=torch.float32)
            with torch.no_grad():
                reconstructed = self._model(tensor)
                loss = torch.mean((tensor - reconstructed) ** 2).item()
            return round(loss, 4)

        centered = []
        columns = list(zip(*windows))
        baselines = [mean(column) for column in columns]
        for row in windows:
            centered.append(sum(abs(value - baseline) for value, baseline in zip(row, baselines)))
        return round(mean(centered), 4)


class CommunityHealthClusterer:
    """Hourly community-level grouping with DBSCAN fallback."""

    def classify(self, samples: list[HealthSample]) -> dict[str, list[str]]:
        if not samples:
            return {"healthy": [], "attention": [], "danger": []}

        if DBSCAN:
            vectors = []
            for sample in samples:
                systolic, diastolic = sample.blood_pressure_pair
                vectors.append([sample.heart_rate, sample.temperature, sample.blood_oxygen, systolic, diastolic])
            labels = DBSCAN(eps=8.0, min_samples=2).fit_predict(vectors)
            grouped = {"healthy": [], "attention": [], "danger": []}
            for label, sample in zip(labels, samples, strict=True):
                if sample.sos_flag or sample.blood_oxygen < 90:
                    grouped["danger"].append(sample.device_mac)
                elif label == -1:
                    grouped["attention"].append(sample.device_mac)
                else:
                    grouped["healthy"].append(sample.device_mac)
            return grouped

        grouped = {"healthy": [], "attention": [], "danger": []}
        for sample in samples:
            systolic, diastolic = sample.blood_pressure_pair
            if sample.sos_flag or sample.blood_oxygen < 90 or systolic > 180 or diastolic > 120:
                grouped["danger"].append(sample.device_mac)
            elif sample.heart_rate > 110 or sample.temperature > 37.6:
                grouped["attention"].append(sample.device_mac)
            else:
                grouped["healthy"].append(sample.device_mac)
        return grouped
