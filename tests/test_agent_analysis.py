from datetime import datetime, timedelta, timezone

from agent.analysis_service import HealthDataAnalysisService
from backend.models.health_model import HealthSample


BASE_TIME = datetime(2026, 3, 13, 8, 0, tzinfo=timezone.utc)


def build_sample(
    *,
    device_mac: str,
    minutes: int,
    heart_rate: int,
    temperature: float,
    blood_oxygen: int,
    blood_pressure: str,
    health_score: int,
    sos_flag: bool = False,
) -> HealthSample:
    return HealthSample(
        device_mac=device_mac,
        timestamp=BASE_TIME + timedelta(minutes=minutes),
        heart_rate=heart_rate,
        temperature=temperature,
        blood_oxygen=blood_oxygen,
        blood_pressure=blood_pressure,
        battery=72,
        sos_flag=sos_flag,
        health_score=health_score,
    )


def test_device_summary_reports_risk_and_recommendations() -> None:
    service = HealthDataAnalysisService()
    samples = [
        build_sample(
            device_mac="53:57:08:00:00:01",
            minutes=0,
            heart_rate=96,
            temperature=36.8,
            blood_oxygen=95,
            blood_pressure="132/84",
            health_score=83,
        ),
        build_sample(
            device_mac="53:57:08:00:00:01",
            minutes=30,
            heart_rate=118,
            temperature=38.2,
            blood_oxygen=91,
            blood_pressure="168/102",
            health_score=61,
        ),
        build_sample(
            device_mac="53:57:08:00:00:01",
            minutes=60,
            heart_rate=126,
            temperature=38.6,
            blood_oxygen=88,
            blood_pressure="172/108",
            health_score=55,
            sos_flag=True,
        ),
    ]

    summary = service.summarize_device(samples)

    assert summary["risk_level"] == "high"
    assert "sos_active" in summary["risk_flags"]
    assert summary["event_counts"]["blood_oxygen_critical"] >= 1
    assert summary["recommendations"]


def test_community_summary_prioritizes_high_risk_devices() -> None:
    service = HealthDataAnalysisService()
    histories = {
        "53:57:08:00:00:01": [
            build_sample(
                device_mac="53:57:08:00:00:01",
                minutes=0,
                heart_rate=90,
                temperature=36.7,
                blood_oxygen=96,
                blood_pressure="128/80",
                health_score=86,
            ),
            build_sample(
                device_mac="53:57:08:00:00:01",
                minutes=45,
                heart_rate=122,
                temperature=38.4,
                blood_oxygen=89,
                blood_pressure="170/104",
                health_score=58,
                sos_flag=True,
            ),
        ],
        "53:57:08:00:00:02": [
            build_sample(
                device_mac="53:57:08:00:00:02",
                minutes=0,
                heart_rate=76,
                temperature=36.5,
                blood_oxygen=98,
                blood_pressure="122/78",
                health_score=90,
            ),
            build_sample(
                device_mac="53:57:08:00:00:02",
                minutes=45,
                heart_rate=78,
                temperature=36.6,
                blood_oxygen=97,
                blood_pressure="124/80",
                health_score=88,
            ),
        ],
    }

    summary = service.summarize_community_history(histories)

    assert summary["device_count"] == 2
    assert summary["risk_distribution"]["high"] == 1
    assert summary["priority_devices"][0]["device_mac"] == "53:57:08:00:00:01"
