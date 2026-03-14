from __future__ import annotations

from fastapi import APIRouter

from backend.dependencies import get_care_service
from backend.models.care_model import CareDirectory


router = APIRouter(prefix="/care", tags=["care"])


@router.get("/directory", response_model=CareDirectory)
async def get_care_directory() -> CareDirectory:
    return get_care_service().get_directory()


@router.get("/directory/family/{family_id}", response_model=CareDirectory)
async def get_family_directory(family_id: str) -> CareDirectory:
    return get_care_service().get_family_directory(family_id)
