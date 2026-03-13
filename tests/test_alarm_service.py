from ai.anomaly_detector import RealtimeAnomalyDetector
from backend.models.health_model import HealthSample


def test_alarm_detector_raises_sos_alarm() -> None:
    detector = RealtimeAnomalyDetector()
    sample = HealthSample(
        device_mac='53:57:08:00:00:01',
        heart_rate=128,
        temperature=38.8,
        blood_oxygen=89,
        blood_pressure='186/122',
        battery=54,
        sos_flag=True,
    )

    alarms = detector.evaluate(sample)
    assert alarms
    assert any(alarm.alarm_type.value == 'sos' for alarm in alarms)
