from __future__ import annotations

from collections import OrderedDict

from backend.models.device_model import DeviceRecord, DeviceRegisterRequest, DeviceStatus


class DeviceService:
    """Tracks device registration and lightweight status in memory."""

    def __init__(self) -> None:
        self._devices: OrderedDict[str, DeviceRecord] = OrderedDict()

    def seed_devices(self, devices: list[DeviceRecord]) -> None:
        for device in devices:
            self._devices[device.mac_address] = device

    def list_devices(self) -> list[DeviceRecord]:
        return list(self._devices.values())

    def get_device(self, mac_address: str) -> DeviceRecord | None:
        return self._devices.get(mac_address.upper())

    def register_device(self, payload: DeviceRegisterRequest) -> DeviceRecord:
        record = DeviceRecord(
            mac_address=payload.mac_address,
            device_name=payload.device_name,
            user_id=payload.user_id,
        )
        self._devices[record.mac_address] = record
        return record

    def ensure_device(self, mac_address: str, device_name: str = "T10-WATCH") -> DeviceRecord:
        existing = self.get_device(mac_address)
        if existing:
            return existing
        request = DeviceRegisterRequest(mac_address=mac_address, device_name=device_name)
        return self.register_device(request)

    def update_status(self, mac_address: str, status: DeviceStatus) -> DeviceRecord | None:
        device = self.get_device(mac_address)
        if not device:
            return None
        updated = device.model_copy(update={"status": status})
        self._devices[mac_address.upper()] = updated
        return updated
