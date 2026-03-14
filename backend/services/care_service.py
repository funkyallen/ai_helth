from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from backend.models.auth_model import (
    AuthAccountPreview,
    LoginResponse,
    SessionUser,
)
from backend.models.care_model import CareDirectory, CommunityProfile, ElderProfile, FamilyProfile
from backend.models.device_model import DeviceRecord
from backend.models.user_model import UserRole
from backend.services.device_service import DeviceService


ELDER_NAME_POOL = [
    "周秀兰",
    "王德福",
    "陈桂香",
    "李建国",
    "刘淑华",
    "孙景明",
    "赵春梅",
    "吴永昌",
    "郑玉琴",
    "胡志强",
    "郭美玲",
    "谢安平",
]

FAMILY_NAME_POOL = [
    "周敏",
    "王浩",
    "陈晨",
    "李娜",
    "刘宇",
    "孙玥",
    "赵琳",
    "吴越",
    "郑琪",
    "胡涛",
]

RELATIONSHIP_POOL = ["女儿", "儿子", "外孙女", "侄女", "儿媳", "女婿"]


def _pick_from_pool(pool: list[str], index: int, fallback_prefix: str) -> str:
    if not pool:
        return f"{fallback_prefix}{index + 1}"
    return pool[index % len(pool)]


def _build_phone(index: int) -> str:
    return f"1380000{str(1200 + index)[-4:]}"


@dataclass(slots=True)
class AccountRecord:
    username: str
    password: str
    user: SessionUser


class CareService:
    """Maintains a deterministic care directory and lightweight demo auth sessions."""

    def __init__(self, device_service: DeviceService) -> None:
        self._device_service = device_service
        self._session_store: dict[str, SessionUser] = {}
        self._session_expiry: dict[str, datetime] = {}
        self._session_ttl = timedelta(hours=12)

    def get_directory(self) -> CareDirectory:
        devices = self._device_service.list_devices()
        return self._build_directory(devices)

    def get_family_directory(self, family_id: str) -> CareDirectory:
        directory = self.get_directory()
        family = next((item for item in directory.families if item.id == family_id), None)
        if not family:
            return CareDirectory(community=directory.community, elders=[], families=[])
        elder_set = set(family.elder_ids)
        elders = [elder for elder in directory.elders if elder.id in elder_set]
        return CareDirectory(
            community=directory.community,
            elders=elders,
            families=[family],
        )

    def list_auth_accounts(self) -> list[AuthAccountPreview]:
        records = self._build_accounts()
        return [
            AuthAccountPreview(
                username=record.username,
                display_name=record.user.name,
                role=record.user.role,
                family_id=record.user.family_id,
                community_id=record.user.community_id,
            )
            for record in records
        ]

    def login(self, username: str, password: str) -> LoginResponse | None:
        username = username.strip().lower()
        record = next((item for item in self._build_accounts() if item.username == username), None)
        if not record or record.password != password:
            return None
        token = str(uuid4())
        self._session_store[token] = record.user
        self._session_expiry[token] = datetime.now(timezone.utc) + self._session_ttl
        return LoginResponse(
            token=token,
            user=record.user,
            expires_at=self._session_expiry[token],
        )

    def resolve_session(self, token: str) -> SessionUser | None:
        token = token.strip()
        if not token:
            return None
        expires_at = self._session_expiry.get(token)
        if not expires_at:
            return None
        if expires_at < datetime.now(timezone.utc):
            self._session_expiry.pop(token, None)
            self._session_store.pop(token, None)
            return None
        return self._session_store.get(token)

    def _build_accounts(self) -> list[AccountRecord]:
        directory = self.get_directory()
        community_user = SessionUser(
            id="user-community-admin",
            username="community_admin",
            name=f"{directory.community.name}值守台",
            role=UserRole.COMMUNITY,
            community_id=directory.community.id,
            family_id=None,
        )
        records = [
            AccountRecord(
                username="community_admin",
                password="123456",
                user=community_user,
            ),
        ]
        for family in directory.families:
            records.append(
                AccountRecord(
                    username=family.login_username.lower(),
                    password="123456",
                    user=SessionUser(
                        id=f"user-{family.id}",
                        username=family.login_username.lower(),
                        name=family.name,
                        role=UserRole.FAMILY,
                        community_id=directory.community.id,
                        family_id=family.id,
                    ),
                ),
            )
        return records

    def _build_directory(self, devices: list[DeviceRecord]) -> CareDirectory:
        sorted_devices = sorted(devices, key=lambda item: item.mac_address)
        community_id = "community-haitang"
        community = CommunityProfile(
            id=community_id,
            name="海棠社区康养中心",
            address="海棠路 68 号",
            manager="张晓慧",
            hotline="400-810-6868",
        )
        elders: list[ElderProfile] = []
        family_map: dict[str, FamilyProfile] = {}

        for index, device in enumerate(sorted_devices):
            family_index = index // 2
            family_id = f"family-{family_index + 1}"
            if family_id not in family_map:
                family_map[family_id] = FamilyProfile(
                    id=family_id,
                    name=_pick_from_pool(FAMILY_NAME_POOL, family_index, "子女"),
                    relationship=_pick_from_pool(RELATIONSHIP_POOL, family_index, "家属"),
                    phone=_build_phone(family_index),
                    community_id=community_id,
                    elder_ids=[],
                    login_username=f"family{family_index + 1:02d}",
                )
            elder = ElderProfile(
                id=f"elder-{index + 1}",
                name=_pick_from_pool(ELDER_NAME_POOL, index, "老人"),
                age=67 + (index % 17),
                apartment=f"{index // 3 + 1} 栋 {100 + (index % 12)} 室",
                community_id=community_id,
                device_mac=device.mac_address,
                family_ids=[family_id],
            )
            elders.append(elder)
            family_map[family_id].elder_ids.append(elder.id)

        families = list(family_map.values())
        return CareDirectory(community=community, elders=elders, families=families)
