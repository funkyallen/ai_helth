from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import datetime, timezone

from backend.models.device_model import DeviceRecord
from backend.models.health_model import HealthSample, IngestionSource


@dataclass(slots=True)
class DevicePersona:
    mac_address: str
    heart_rate_base: int
    temperature_base: float
    blood_oxygen_base: int
    systolic_base: int
    diastolic_base: int
    battery: int


class SyntheticHealthDataGenerator:
    """Generates realistic elder-care vital signs for demos, tests and model warm-up."""

    def __init__(self, device_count: int = 10, mac_prefix: str = "53:57:08", seed: int = 42) -> None:
        self._rng = random.Random(seed)
        self._device_count = device_count
        self._mac_prefix = mac_prefix
        self._personas = [self._build_persona(index) for index in range(device_count)]

    @property
    def personas(self) -> list[DevicePersona]:
        return self._personas

    def build_devices(self) -> list[DeviceRecord]:
        return [
            DeviceRecord(mac_address=persona.mac_address, device_name="T10-WATCH")
            for persona in self._personas
        ]

    def next_sample(self, now: datetime | None = None) -> HealthSample:
        now = now or datetime.now(timezone.utc)
        persona = self._rng.choice(self._personas)
        hour_phase = math.sin((now.hour / 24) * math.pi * 2)

        heart_rate = persona.heart_rate_base + round(hour_phase * 6) + self._rng.randint(-4, 4)
        temperature = round(persona.temperature_base + hour_phase * 0.2 + self._rng.uniform(-0.15, 0.15), 1)
        blood_oxygen = persona.blood_oxygen_base + self._rng.randint(-1, 1)
        systolic = persona.systolic_base + self._rng.randint(-5, 5)
        diastolic = persona.diastolic_base + self._rng.randint(-4, 4)
        sos_flag = False

        scenario_roll = self._rng.random()
        if scenario_roll > 0.99:
            sos_flag = True
            heart_rate = min(190, heart_rate + self._rng.randint(18, 34))
            blood_oxygen = max(84, blood_oxygen - self._rng.randint(6, 10))
            temperature = round(min(39.2, temperature + self._rng.uniform(0.8, 1.4)), 1)
        elif scenario_roll > 0.95:
            heart_rate = min(188, heart_rate + self._rng.randint(22, 36))
            blood_oxygen = max(86, blood_oxygen - self._rng.randint(4, 8))
            systolic += self._rng.randint(18, 35)
            diastolic += self._rng.randint(12, 22)
            temperature = round(min(39.0, temperature + self._rng.uniform(0.6, 1.2)), 1)
        elif scenario_roll > 0.80:
            heart_rate = min(132, heart_rate + self._rng.randint(6, 14))
            blood_oxygen = max(91, blood_oxygen - self._rng.randint(1, 4))
            systolic += self._rng.randint(4, 12)
            diastolic += self._rng.randint(2, 8)
            temperature = round(min(38.1, temperature + self._rng.uniform(0.1, 0.5)), 1)

        persona.battery = max(18, persona.battery - self._rng.choice([0, 0, 1]))
        return HealthSample(
            device_mac=persona.mac_address,
            timestamp=now,
            heart_rate=heart_rate,
            temperature=temperature,
            blood_oxygen=blood_oxygen,
            blood_pressure=f"{systolic}/{diastolic}",
            battery=persona.battery,
            sos_flag=sos_flag,
            source=IngestionSource.MOCK,
        )

    def encode_packet_pair(self, sample: HealthSample) -> tuple[str, str]:
        """Encodes a sample into the demo packet layout used by iot/parser.py."""
        systolic, diastolic = sample.blood_pressure_pair
        flags = 0x01 if sample.sos_flag else 0x00
        event_code = 0x02 if sample.sos_flag else 0x00
        temperature_raw = int(round(sample.temperature * 100))
        merged_payload = bytes(
            [
                sample.heart_rate,
                (temperature_raw >> 8) & 0xFF,
                temperature_raw & 0xFF,
                sample.blood_oxygen,
                systolic,
                diastolic,
                sample.battery,
                flags,
                event_code,
                0x00,
                0x00,
                0x00,
            ]
        )
        header = bytes.fromhex("AA55AA55AA55AA55AA55AA55")
        packet_a = header + bytes.fromhex("1803") + merged_payload[:6]
        packet_b = header + bytes.fromhex("0318") + merged_payload[6:]
        return packet_a.hex().upper(), packet_b.hex().upper()

    def _build_persona(self, index: int) -> DevicePersona:
        suffix = f"{index + 1:06X}"
        mac = ":".join([*self._mac_prefix.split(":"), suffix[0:2], suffix[2:4], suffix[4:6]])
        return DevicePersona(
            mac_address=mac,
            heart_rate_base=self._rng.randint(62, 84),
            temperature_base=round(self._rng.uniform(36.2, 36.8), 1),
            blood_oxygen_base=self._rng.randint(95, 99),
            systolic_base=self._rng.randint(108, 128),
            diastolic_base=self._rng.randint(68, 82),
            battery=self._rng.randint(72, 100),
        )
