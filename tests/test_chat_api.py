from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from backend.dependencies import get_stream_service
from backend.main import app
from backend.models.health_model import HealthSample, IngestionSource


BASE_TIME = datetime(2026, 3, 14, 8, 0, tzinfo=timezone.utc)


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
        battery=76,
        sos_flag=sos_flag,
        source=IngestionSource.MOCK,
        health_score=health_score,
    )


def seed_stream(*samples: HealthSample) -> None:
    stream = get_stream_service()
    for sample in samples:
        stream.publish(sample)


def test_device_analysis_endpoint_returns_structured_payload() -> None:
    device_mac = '53:57:08:AA:00:11'
    seed_stream(
        build_sample(
            device_mac=device_mac,
            minutes=0,
            heart_rate=94,
            temperature=36.8,
            blood_oxygen=96,
            blood_pressure='130/82',
            health_score=84,
        ),
        build_sample(
            device_mac=device_mac,
            minutes=45,
            heart_rate=122,
            temperature=38.1,
            blood_oxygen=90,
            blood_pressure='168/100',
            health_score=60,
            sos_flag=True,
        ),
    )

    client = TestClient(app)
    response = client.post(
        '/api/v1/chat/analyze/device',
        json={
            'device_mac': device_mac,
            'question': 'Analyze recent health data thoroughly.',
            'mode': 'local',
            'history_minutes': 60 * 24 * 30,
            'history_limit': 50,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload['scope'] == 'device'
    assert payload['mode'] in {'local', 'cloud'}
    assert isinstance(payload['analysis'], dict)
    assert payload['analysis']['risk_level'] == 'high'
    assert isinstance(payload['answer'], str) and payload['answer']


def test_community_analysis_endpoint_returns_priority_devices() -> None:
    high_risk_mac = '53:57:08:AA:00:21'
    stable_mac = '53:57:08:AA:00:22'
    seed_stream(
        build_sample(
            device_mac=high_risk_mac,
            minutes=0,
            heart_rate=118,
            temperature=37.9,
            blood_oxygen=91,
            blood_pressure='160/98',
            health_score=64,
        ),
        build_sample(
            device_mac=high_risk_mac,
            minutes=30,
            heart_rate=126,
            temperature=38.4,
            blood_oxygen=88,
            blood_pressure='172/108',
            health_score=55,
            sos_flag=True,
        ),
        build_sample(
            device_mac=stable_mac,
            minutes=0,
            heart_rate=75,
            temperature=36.5,
            blood_oxygen=98,
            blood_pressure='122/78',
            health_score=91,
        ),
        build_sample(
            device_mac=stable_mac,
            minutes=30,
            heart_rate=76,
            temperature=36.6,
            blood_oxygen=97,
            blood_pressure='124/80',
            health_score=89,
        ),
    )

    client = TestClient(app)
    response = client.post(
        '/api/v1/chat/analyze/community',
        json={
            'question': 'Summarize recent health data across community devices.',
            'mode': 'local',
            'history_minutes': 60 * 24 * 30,
            'per_device_limit': 50,
            'device_macs': [high_risk_mac, stable_mac],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload['scope'] == 'community'
    assert isinstance(payload['analysis'], dict)
    assert payload['analysis']['device_count'] == 2
    assert payload['analysis']['priority_devices'][0]['device_mac'] == high_risk_mac
    assert isinstance(payload['answer'], str) and payload['answer']
