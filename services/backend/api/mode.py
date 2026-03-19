"""
Trading Mode Toggle API

GET  /wallet/mode  — returns current mode + balance info for the UI
POST /wallet/mode  — switches mode with a user-confirmation warning

Switching paper → real:
  - No KYC required
  - No minimum balance required
  - Only gate: confirmed=True must be sent (user acknowledged the warning)
  - Frontend shows a clear warning modal before sending confirmed=True

Switching real → paper:
  - Always instant, no gates, no confirmation needed
"""

import logging
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from services.backend.data.database import get_session
from services.backend.core.paper_trading import (
    _ensure_wallet_config,
    get_user_by_wallet,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Trading Mode"], redirect_slashes=False)


# ─── MODELS ──────────────────────────────────────────────────────────────────

class ModeToggleRequest(BaseModel):
    wallet_address: Optional[str] = None
    telegram_user_id: Optional[str] = None
    mode: str            # 'paper' or 'real'
    confirmed: bool = False  # Must be True for paper → real


# ─── HELPER ──────────────────────────────────────────────────────────────────

def _resolve_config(wallet_address, telegram_user_id, session):
    if not wallet_address and not telegram_user_id:
        raise HTTPException(
            status_code=400,
            detail="Provide either wallet_address or telegram_user_id.",
        )
    tid = telegram_user_id
    if wallet_address and not telegram_user_id:
        user = get_user_by_wallet(wallet_address.lower(), session)
        tid = (user.telegram_id or user.wallet_address) if user else wallet_address.lower()
    return _ensure_wallet_config(str(tid), session)


# ─── ENDPOINTS ───────────────────────────────────────────────────────────────

@router.get("/wallet/mode")
def get_mode(
    wallet_address: Optional[str] = None,
    telegram_user_id: Optional[str] = None,
    session: Session = Depends(get_session),
):
    """
    GET /wallet/mode

    Returns the user's current trading mode and real USDC balance.
    The frontend uses this to render the toggle pill and warning modal.
    """
    config = _resolve_config(wallet_address, telegram_user_id, session)
    return {
        "trading_mode":      config.trading_mode,
        "real_balance_usdc": round(config.real_balance_usdc, 2),
        "can_switch_to_real": True,   # Always allowed — just requires confirmation
    }


@router.post("/wallet/mode")
def set_mode(
    request: ModeToggleRequest,
    session: Session = Depends(get_session),
):
    """
    POST /wallet/mode

    Switch trading mode.

    paper → real:
      Requires confirmed=True (user clicked through the warning modal).
      No KYC, no minimum balance.

    real → paper:
      Always instant. confirmed not required.
    """
    config = _resolve_config(request.wallet_address, request.telegram_user_id, session)

    requested_mode = request.mode.lower().strip()
    if requested_mode not in ("paper", "real"):
        raise HTTPException(status_code=400, detail="mode must be 'paper' or 'real'.")

    # ── real → paper: always instant ─────────────────────────────────────────
    if requested_mode == "paper":
        config.trading_mode = "paper"
        config.updated_at   = datetime.utcnow()
        session.add(config)
        session.commit()
        logger.info(f"[mode] {config.telegram_user_id} → PAPER")
        return {
            "status":       "ok",
            "trading_mode": "paper",
            "message":      "Switched to paper trading. No real money involved.",
        }

    # ── paper → real: only requires explicit confirmation ────────────────────
    if not request.confirmed:
        raise HTTPException(
            status_code=403,
            detail={
                "message": "Confirmation required to enable real trading.",
                "hint":    "Set confirmed=true after the user acknowledges the warning.",
            },
        )

    config.trading_mode = "real"
    config.updated_at   = datetime.utcnow()
    session.add(config)
    session.commit()

    logger.info(f"[mode] {config.telegram_user_id} → REAL")
    return {
        "status":       "ok",
        "trading_mode": "real",
        "message":      "Real trading enabled. All trades will use real USDC on Base.",
    }
