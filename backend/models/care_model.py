from __future__ import annotations

from pydantic import BaseModel, Field


class CommunityProfile(BaseModel):
    id: str
    name: str
    address: str
    manager: str
    hotline: str


class ElderProfile(BaseModel):
    id: str
    name: str
    age: int = Field(ge=50, le=120)
    apartment: str
    community_id: str
    device_mac: str
    family_ids: list[str] = Field(default_factory=list)


class FamilyProfile(BaseModel):
    id: str
    name: str
    relationship: str
    phone: str
    community_id: str
    elder_ids: list[str] = Field(default_factory=list)
    login_username: str


class CareDirectory(BaseModel):
    community: CommunityProfile
    elders: list[ElderProfile] = Field(default_factory=list)
    families: list[FamilyProfile] = Field(default_factory=list)
