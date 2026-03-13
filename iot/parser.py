from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

from backend.models.health_model import HealthSample, IngestionSource


class PacketKind(str, Enum):
    BROADCAST = "broadcast"
    RESPONSE_A = "response_a"
    RESPONSE_B = "response_b"
    UNKNOWN = "unknown"


@dataclass(slots=True)
class PacketLayout:
    marker_offset: int = 12
    header_length: int = 14
    response_a_marker: bytes = bytes.fromhex("1803")
    response_b_marker: bytes = bytes.fromhex("0318")
    heart_rate_offset: int = 0
    temperature_offset: int = 1
    blood_oxygen_offset: int = 3
    systolic_offset: int = 4
    diastolic_offset: int = 5
    battery_offset: int = 6
    flags_offset: int = 7
    event_code_offset: int = 8


@dataclass(slots=True)
class PartialPacket:
    first_seen: datetime
    packet_a: bytes | None = None
    packet_b: bytes | None = None
    raw_a: str | None = None
    raw_b: str | None = None


class T10PacketParser:
    """
    Parser for the T10 bracelet.

    The competition manual confirms:
    - response frames are split into two packets,
    - the marker at byte 13-14 distinguishes `0x1803` and `0x0318`,
    - SOS is triggered by a 5-second long press and keeps broadcasting for 15 seconds.

    The exact field positions vary by firmware. This parser therefore keeps the merge rule strict,
    while the payload layout is configurable and used consistently by the project simulator.
    """

    def __init__(
        self,
        layout: PacketLayout | None = None,
        merge_timeout_seconds: float = 2.5,
        sos_window_seconds: int = 15,
    ) -> None:
        self._layout = layout or PacketLayout()
        self._merge_timeout = merge_timeout_seconds
        self._partials: dict[str, PartialPacket] = {}
        self._sos_events: dict[str, deque[datetime]] = defaultdict(deque)
        self._sos_window = timedelta(seconds=sos_window_seconds)

    def feed(
        self,
        device_mac: str,
        payload: str | bytes,
        *,
        source: IngestionSource = IngestionSource.BLE,
        timestamp: datetime | None = None,
    ) -> HealthSample | None:
        timestamp = timestamp or datetime.now(timezone.utc)
        device_mac = device_mac.upper()
        packet = self._normalize_payload(payload)
        kind = self.identify_packet(packet)

        if kind is PacketKind.UNKNOWN:
            return None

        if kind is PacketKind.BROADCAST:
            merged = packet[self._layout.header_length :]
            return self._decode(device_mac, merged, timestamp, source, raw_a=packet.hex().upper())

        partial = self._partials.get(device_mac)
        if not partial or timestamp - partial.first_seen > timedelta(seconds=self._merge_timeout):
            partial = PartialPacket(first_seen=timestamp)

        if kind is PacketKind.RESPONSE_A:
            partial.packet_a = packet
            partial.raw_a = packet.hex().upper()
        else:
            partial.packet_b = packet
            partial.raw_b = packet.hex().upper()

        self._partials[device_mac] = partial
        if not partial.packet_a or not partial.packet_b:
            return None

        merged = partial.packet_a[self._layout.header_length :] + partial.packet_b[self._layout.header_length :]
        del self._partials[device_mac]
        return self._decode(
            device_mac,
            merged,
            timestamp,
            source,
            raw_a=partial.raw_a,
            raw_b=partial.raw_b,
        )

    def identify_packet(self, payload: bytes) -> PacketKind:
        if len(payload) <= self._layout.marker_offset + 1:
            return PacketKind.UNKNOWN
        marker = payload[self._layout.marker_offset : self._layout.marker_offset + 2]
        if marker == self._layout.response_a_marker:
            return PacketKind.RESPONSE_A
        if marker == self._layout.response_b_marker:
            return PacketKind.RESPONSE_B
        if len(payload) > self._layout.header_length + self._layout.event_code_offset:
            return PacketKind.BROADCAST
        return PacketKind.UNKNOWN

    @staticmethod
    def _normalize_payload(payload: str | bytes) -> bytes:
        if isinstance(payload, bytes):
            return payload
        compact = payload.replace(" ", "").replace(":", "").replace("-", "")
        return bytes.fromhex(compact)

    def _decode(
        self,
        device_mac: str,
        merged: bytes,
        timestamp: datetime,
        source: IngestionSource,
        *,
        raw_a: str | None = None,
        raw_b: str | None = None,
    ) -> HealthSample | None:
        layout = self._layout
        min_length = layout.event_code_offset + 1
        if len(merged) < min_length:
            return None

        heart_rate = merged[layout.heart_rate_offset]
        temperature_raw = (merged[layout.temperature_offset] << 8) | merged[layout.temperature_offset + 1]
        temperature = round(temperature_raw / 100.0, 1)
        blood_oxygen = merged[layout.blood_oxygen_offset]
        systolic = merged[layout.systolic_offset]
        diastolic = merged[layout.diastolic_offset]
        battery = merged[layout.battery_offset]
        flags = merged[layout.flags_offset]
        event_code = merged[layout.event_code_offset]
        sos_flag = bool(flags & 0x01) or event_code == 0x02 or self._register_sos(device_mac, timestamp, flags, event_code)

        return HealthSample(
            device_mac=device_mac,
            timestamp=timestamp,
            heart_rate=heart_rate,
            temperature=temperature,
            blood_oxygen=blood_oxygen,
            blood_pressure=f"{systolic}/{diastolic}",
            battery=battery,
            sos_flag=sos_flag,
            source=source,
            raw_packet_a=raw_a,
            raw_packet_b=raw_b,
        )

    def _register_sos(self, device_mac: str, timestamp: datetime, flags: int, event_code: int) -> bool:
        if not (flags & 0x01 or event_code == 0x02):
            return False
        events = self._sos_events[device_mac]
        events.append(timestamp)
        while events and timestamp - events[0] > self._sos_window:
            events.popleft()
        return True

    def parse_dict(self, device_mac: str, payload: str | bytes, **kwargs: Any) -> dict[str, Any] | None:
        sample = self.feed(device_mac, payload, **kwargs)
        return sample.model_dump(mode="json") if sample else None
