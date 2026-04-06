from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from services.backend.core.telegram_users import (
    get_telegram_profile,
    set_language,
    set_pending_premium_market,
    update_permissions,
    upsert_telegram_profile,
)
from services.backend.data.database import get_session
from services.backend.api.auth import get_current_user

router = APIRouter(tags=["Telegram"])


class TelegramUserUpsertRequest(BaseModel):
    telegram_id: str
    username: Optional[str] = None
    language: Optional[str] = None


class LanguagePreferenceRequest(BaseModel):
    telegram_id: str
    language: str


class PendingPremiumRequest(BaseModel):
    telegram_id: str
    market_id: Optional[str] = None


class PermissionsRequest(BaseModel):
    telegram_user_id: str
    auto_trade: Optional[bool] = None
    limit: Optional[float] = None


@router.post("/telegram/user/upsert")
def telegram_user_upsert(
    request: TelegramUserUpsertRequest,
    session: Session = Depends(get_session),
):
    try:
        profile = upsert_telegram_profile(
            session=session,
            telegram_id=request.telegram_id,
            username=request.username,
            preferred_language=request.language,
        )
        return serialize_profile(profile)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/telegram/user/{telegram_id}")
def telegram_user_get(
    telegram_id: str,
    session: Session = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    profile = get_telegram_profile(session, telegram_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Telegram profile not found")
    return serialize_profile(profile)


@router.post("/telegram/preferences/language")
def telegram_set_language(
    request: LanguagePreferenceRequest,
    session: Session = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    try:
        profile = set_language(session, request.telegram_id, request.language)
        return serialize_profile(profile)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/telegram/session/premium-request")
def telegram_set_pending_premium(
    request: PendingPremiumRequest,
    session: Session = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    try:
        profile = set_pending_premium_market(session, request.telegram_id, request.market_id)
        return serialize_profile(profile)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/telegram/permissions/{telegram_id}")
def telegram_get_permissions(
    telegram_id: str,
    session: Session = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    profile = get_telegram_profile(session, telegram_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Telegram profile not found")
    return {
        "telegram_user_id": profile.telegram_id,
        "auto_trade": profile.auto_trade_enabled,
        "limit": profile.auto_trade_limit,
    }


@router.post("/permissions")
def permissions_update(
    request: PermissionsRequest,
    session: Session = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    try:
        profile = update_permissions(
            session=session,
            telegram_id=request.telegram_user_id,
            auto_trade=request.auto_trade,
            limit=request.limit,
        )
        return {
            "telegram_user_id": profile.telegram_id,
            "auto_trade": profile.auto_trade_enabled,
            "limit": profile.auto_trade_limit,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


def serialize_profile(profile) -> dict:
    return {
        "telegram_id": profile.telegram_id,
        "user_id": profile.user_id,
        "username": profile.username,
        "language": profile.preferred_language,
        "pending_premium_market_id": profile.pending_premium_market_id,
        "auto_trade_enabled": profile.auto_trade_enabled,
        "auto_trade_limit": profile.auto_trade_limit,
        "created_at": profile.created_at.isoformat() if profile.created_at else None,
        "updated_at": profile.updated_at.isoformat() if profile.updated_at else None,
    }
