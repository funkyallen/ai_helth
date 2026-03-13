from __future__ import annotations

import json
from collections.abc import Awaitable, Callable

from backend.models.health_model import HealthSample, IngestionSource
from iot.parser import T10PacketParser

try:
    import paho.mqtt.client as mqtt
except ImportError:
    mqtt = None


class MQTTGatewayListener:
    """MQTT gateway adapter for ESP32 or dedicated BLE relay hardware."""

    def __init__(self, parser: T10PacketParser) -> None:
        self._parser = parser

    def run(
        self,
        broker_host: str,
        topic: str,
        on_sample_sync: Callable[[HealthSample], Awaitable[None]] | None = None,
    ) -> None:
        if mqtt is None:
            raise RuntimeError("paho-mqtt 未安装，无法启用 MQTT 网关模式。")

        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

        def handle_message(_client, _userdata, message):
            payload = json.loads(message.payload.decode("utf-8"))
            sample = self._parser.feed(
                payload["device_mac"],
                payload["hex_payload"],
                source=IngestionSource.MQTT,
            )
            if sample and on_sample_sync:
                import asyncio

                asyncio.create_task(on_sample_sync(sample))

        client.on_message = handle_message
        client.connect(broker_host)
        client.subscribe(topic)
        client.loop_forever()
