from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException

from backend.dependencies import get_care_service
from backend.models.auth_model import AuthAccountPreview, LoginRequest, LoginResponse, SessionUser


router = APIRouter(prefix="/auth", tags=["auth"])


def _extract_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token.strip()


@router.get("/mock-accounts", response_model=list[AuthAccountPreview])
async def list_mock_accounts() -> list[AuthAccountPreview]:
    return get_care_service().list_auth_accounts()


@router.post("/mock-login", response_model=LoginResponse)
async def mock_login(payload: LoginRequest) -> LoginResponse:
    result = get_care_service().login(payload.username, payload.password)
    if not result:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return result


@router.get("/me", response_model=SessionUser)
async def me(authorization: str | None = Header(default=None)) -> SessionUser:
    token = _extract_token(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="缺少认证信息")
    user = get_care_service().resolve_session(token)
    if not user:
        raise HTTPException(status_code=401, detail="登录状态已失效")
    return user
