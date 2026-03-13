from __future__ import annotations

from collections.abc import Awaitable, Callable

from backend.models.health_model import HealthSample, IngestionSource
from iot.parser import T10PacketParser

try:
    import serial
except ImportError:
    serial = None


class SerialGatewayReader:
    """Serial adapter for nRF52832 transparent transmission collectors."""

    def __init__(self, parser: T10PacketParser) -> None:
        self._parser = parser

    def run(
        self,
        port: str,
        baudrate: int,
        device_mac: str,
        on_sample_sync: Callable[[HealthSample], Awaitable[None]] | None = None,
    ) -> None:
        if serial is None:
            raise RuntimeError("pyserial 未安装，无法启用串口采集模式。")

        with serial.Serial(port=port, baudrate=baudrate, timeout=1) as connection:
            while True:
                line = connection.readline().decode("utf-8", errors="ignore").strip()
                if not line:
                    continue
                sample = self._parser.feed(device_mac, line, source=IngestionSource.SERIAL)
                if sample and on_sample_sync:
                    import asyncio

                    asyncio.create_task(on_sample_sync(sample))
