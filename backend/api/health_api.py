from __future__ import annotations

from statistics import mean

from fastapi import APIRouter, HTTPException, Query

from backend.dependencies import (
    get_community_clusterer,
    get_intelligent_scorer,
    get_stream_service,
    ingest_sample,
)
from backend.models.health_model import HealthSample, HealthTrendPoint, IngestResponse


router = APIRouter(prefix="/health", tags=["health"])


@router.post("/ingest", response_model=IngestResponse)
async def ingest_health_sample(payload: HealthSample) -> IngestResponse:
    return await ingest_sample(payload)


@router.get("/realtime/{device_mac}", response_model=HealthSample)
async def get_realtime_sample(device_mac: str) -> HealthSample:
    sample = get_stream_service().latest(device_mac)
    if not sample:
        raise HTTPException(status_code=404, detail="No realtime sample available")
    return sample


@router.get("/trend/{device_mac}", response_model=list[HealthTrendPoint])
async def get_health_trend(
    device_mac: str,
    minutes: int = Query(default=60, ge=5, le=10080),
    limit: int = Query(default=120, ge=10, le=1000),
) -> list[HealthTrendPoint]:
    return get_stream_service().trend(device_mac, minutes=minutes, limit=limit)


@router.get("/community/overview")
async def get_community_overview() -> dict[str, object]:
    samples = get_stream_service().latest_samples()
    grouped = get_community_clusterer().classify(samples)
    score = 0.0
    if samples:
        windows = [
            [
                sample.heart_rate,
                sample.temperature,
                sample.blood_oxygen,
                mean(sample.blood_pressure_pair),
            ]
            for sample in samples
        ]
        score = get_intelligent_scorer().score_sequence(windows)
    return {
        "clusters": grouped,
        "device_count": len(samples),
        "intelligent_anomaly_score": score,
    }
