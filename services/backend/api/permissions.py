"""
permissions.py — POST /permissions

Allows users (via the Telegram bot) to set their auto-trade preferences.
The AutoTradeEngine in executor.py reads from this table on every trade decision.

Routes:
    POST /permissions        — create or update a user's permission record
    GET  /permissions/{id}   — read current permissions for a user

Telegram bot commands that call this:
    /enable_autotrade    → auto_trade_enabled=True
    /disable_autotrade   → auto_trade_enabled=False
    /set_limit <amount>  → max_bet_size=<amount>
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from sqlmodel import Session, select

from services.backend.data.database import engine
from services.backend.data.models import UserPermission

router = APIRouter(prefix="/permissions", tags=["Permissions"])


# ─────────────────────────────────────────────────────────────
# Request / Response Models
# ─────────────────────────────────────────────────────────────

class PermissionRequest(BaseModel):
    telegram_user_id: str
    auto_trade_enabled: Optional[bool]   = None
    max_bet_size: Optional[float]        = None
    min_confidence: Optional[float]      = None
    trade_mode: Optional[str]            = None   # "paper" | "real" | "confirm"
    preferred_language: Optional[str]    = None   # "en" | "sw"

class PermissionResponse(BaseModel):
    telegram_user_id: str
    auto_trade_enabled: bool
    trade_mode: str
    max_bet_size: float
    min_confidence: float
    preferred_language: str
    updated_at: datetime


# ─────────────────────────────────────────────────────────────
# POST /permissions  — upsert
# ─────────────────────────────────────────────────────────────

@router.post("", response_model=PermissionResponse)
def upsert_permissions(req: PermissionRequest):
    """
    Creates or updates the UserPermission record for a Telegram user.
    Only fields that are explicitly provided in the request are updated —
    omitted fields keep their current value (or defaults on first create).
    """
    valid_modes = {"paper", "real", "confirm"}
    if req.trade_mode and req.trade_mode not in valid_modes:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid trade_mode '{req.trade_mode}'. Must be one of: {valid_modes}"
        )

    valid_langs = {"en", "sw"}
    if req.preferred_language and req.preferred_language not in valid_langs:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid preferred_language '{req.preferred_language}'. Must be one of: {valid_langs}"
        )

    with Session(engine) as session:
        perm = session.exec(
            select(UserPermission)
            .where(UserPermission.telegram_user_id == req.telegram_user_id)
        ).first()

        if perm is None:
            # First time — create with defaults, then apply any provided fields
            perm = UserPermission(telegram_user_id=req.telegram_user_id)
            session.add(perm)

        # Apply only the fields that were explicitly provided
        if req.auto_trade_enabled is not None:
            perm.auto_trade_enabled = req.auto_trade_enabled
        if req.max_bet_size is not None:
            if req.max_bet_size <= 0:
                raise HTTPException(status_code=400, detail="max_bet_size must be greater than 0")
            perm.max_bet_size = req.max_bet_size
        if req.min_confidence is not None:
            if not (0.0 <= req.min_confidence <= 1.0):
                raise HTTPException(status_code=400, detail="min_confidence must be between 0.0 and 1.0")
            perm.min_confidence = req.min_confidence
        if req.trade_mode is not None:
            perm.trade_mode = req.trade_mode
        if req.preferred_language is not None:
            perm.preferred_language = req.preferred_language

        perm.updated_at = datetime.utcnow()
        session.commit()
        session.refresh(perm)

        return PermissionResponse(
            telegram_user_id=perm.telegram_user_id,
            auto_trade_enabled=perm.auto_trade_enabled,
            trade_mode=perm.trade_mode,
            max_bet_size=perm.max_bet_size,
            min_confidence=perm.min_confidence,
            preferred_language=perm.preferred_language,
            updated_at=perm.updated_at,
        )


# ─────────────────────────────────────────────────────────────
# GET /permissions/{telegram_user_id}  — read current settings
# ─────────────────────────────────────────────────────────────

@router.get("/{telegram_user_id}", response_model=PermissionResponse)
def get_permissions(telegram_user_id: str):
    """
    Returns the current permission settings for a user.
    Returns 404 if the user has never set permissions.
    """
    with Session(engine) as session:
        perm = session.exec(
            select(UserPermission)
            .where(UserPermission.telegram_user_id == telegram_user_id)
        ).first()

        if not perm:
            raise HTTPException(
                status_code=404,
                detail=f"No permissions found for user '{telegram_user_id}'. "
                       f"Use POST /permissions to create them."
            )

        return PermissionResponse(
            telegram_user_id=perm.telegram_user_id,
            auto_trade_enabled=perm.auto_trade_enabled,
            trade_mode=perm.trade_mode,
            max_bet_size=perm.max_bet_size,
            min_confidence=perm.min_confidence,
            preferred_language=perm.preferred_language,
            updated_at=perm.updated_at,
        )
