"""
Trading Mode Toggle API
"""

import logging
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from services.backend.data.database import get_session
from services.backend.core.paper_trading import _ensure_wallet_config, get_user_by_wallet
from services.backend.api.auth import get_current_user
from services.backend.api.wallet import _assert_owns_wallet

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Trading Mode"], redirect_slashes=False)


class ModeToggleRequest(BaseModel):
    wallet_address:   Optional[str] = None
    telegram_user_id: Optional[str] = None
    mode:             str
    confirmed:        bool = False


def _resolve_config(wallet_address, telegram_user_id, session):
    if not wallet_address and not telegram_user_id:
        raise HTTPException(400, "Provide wallet_address or telegram_user_id.")
    tid = telegram_user_id
    if wallet_address and not telegram_user_id:
        user = get_user_by_wallet(wallet_address.lower(), session)
        tid  = (user.telegram_id or user.wallet_address) if user else wallet_address.lower()
    return _ensure_wallet_config(str(tid), session)


@router.get("/wallet/mode")
def get_mode(
    wallet_address:   Optional[str] = None,
    telegram_user_id: Optional[str] = None,
    session:          Session = Depends(get_session),
    current_user:     dict   = Depends(get_current_user),
):
    # If nothing provided, fall back to the JWT wallet
    if not wallet_address and not telegram_user_id:
        wallet_address = current_user.get("wallet")
    if not wallet_address and not telegram_user_id:
        raise HTTPException(400, "Provide wallet_address or telegram_user_id.")

    requested_wallet = (wallet_address or current_user["wallet"]).lower()
    if requested_wallet != current_user["wallet"].lower():
        raise HTTPException(status_code=403, detail="Cannot access mode for another wallet")

    config = _resolve_config(requested_wallet, telegram_user_id, session)
    return {
        "trading_mode":       config.trading_mode,
        "real_balance_usdc":  round(config.real_balance_usdc, 2),
        "can_switch_to_real": True,
    }


@router.post("/wallet/mode")
def set_mode(
    request:      ModeToggleRequest,
    session:      Session = Depends(get_session),
    current_user: dict   = Depends(get_current_user),
):
    # Resolve target wallet
    target_wallet = request.wallet_address or request.telegram_user_id or current_user.get("wallet")
    if not target_wallet:
        raise HTTPException(400, "Provide wallet_address or telegram_user_id.")

    # Ownership check (safe — _assert_owns_wallet handles None jwt_wallet gracefully)
    if request.wallet_address:
        _assert_owns_wallet(request.wallet_address, current_user)

    requested_wallet = (request.wallet_address or current_user.get("wallet") or "").lower() or None
    config = _resolve_config(requested_wallet, request.telegram_user_id, session)

    requested_mode = request.mode.lower().strip()
    if requested_mode not in ("paper", "real"):
        raise HTTPException(400, "mode must be 'paper' or 'real'.")

    if requested_mode == "paper":
        config.trading_mode = "paper"
        config.updated_at   = datetime.utcnow()
        session.add(config)
        session.commit()
        return {"status": "ok", "trading_mode": "paper", "message": "Switched to paper trading."}

    if not request.confirmed:
        raise HTTPException(403, {"message": "Confirmation required.", "hint": "Set confirmed=true."})

    config.trading_mode = "real"
    config.updated_at   = datetime.utcnow()
    session.add(config)
    session.commit()
    return {"status": "ok", "trading_mode": "real", "message": "Real trading enabled."}
