from __future__ import annotations

import asyncio
from contextlib import suppress

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from backend.api.alarm_api import router as alarm_router
from backend.api.chat_api import router as chat_router
from backend.api.device_api import router as device_router
from backend.api.health_api import router as health_router
from backend.config import get_settings
from backend.dependencies import (
    get_data_generator,
    get_settings_dependency,
    get_websocket_manager,
    ingest_sample,
)


settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    debug=settings.debug,
    summary="AIoT elder-care monitoring backend for the 2026 competition project.",
)

app.include_router(device_router, prefix=settings.api_v1_prefix)
app.include_router(health_router, prefix=settings.api_v1_prefix)
app.include_router(alarm_router, prefix=settings.api_v1_prefix)
app.include_router(chat_router, prefix=settings.api_v1_prefix)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok", "app": settings.app_name}


@app.get("/api/v1/system/info")
async def system_info() -> dict[str, object]:
    cfg = get_settings_dependency()
    return {
        "competition_stack": {
            "python": "3.9+",
            "anaconda": "22.9.0",
            "ollama": "0.12.9",
            "qwen_local": "qwen3:1.7b",
            "database": "PostgreSQL 15 / TimescaleDB",
        },
        "configured": {
            "mock_mode": cfg.use_mock_data,
            "mac_prefixes": cfg.allowed_mac_prefixes,
        },
    }


@app.websocket("/ws/health/{device_mac}")
async def health_stream(device_mac: str, websocket: WebSocket) -> None:
    manager = get_websocket_manager()
    await manager.connect_health(device_mac, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect_health(device_mac, websocket)


@app.websocket("/ws/alarms")
async def alarm_stream(websocket: WebSocket) -> None:
    manager = get_websocket_manager()
    await manager.connect_alarm(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect_alarm(websocket)


async def _mock_stream_loop() -> None:
    generator = get_data_generator()
    while True:
        sample = generator.next_sample()
        await ingest_sample(sample)
        await asyncio.sleep(settings.mock_push_interval_seconds)


@app.on_event("startup")
async def on_startup() -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    if settings.use_mock_data:
        app.state.mock_task = asyncio.create_task(_mock_stream_loop())


@app.on_event("shutdown")
async def on_shutdown() -> None:
    task = getattr(app.state, "mock_task", None)
    if task:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
