"""
Trading Mode Toggle API — POST /wallet/mode

Handles switching between paper and real trading modes.
The backend enforces all gates — the frontend just sends the intent.

Gates for switching paper → real:
  1. KYC: kyc_status must be 'approved'
  2. Minimum balance: real_balance_usdc >= 10.0 USDC on Base
  3. Explicit confirmation: request must include confirmed=True

Switching real → paper:
  Always allowed. Instant. No gates.

GET /wallet/mode — returns current mode + gate status for the UI
     so the frontend can show which gates are passed/pending.
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from services.backend.data.database import get_session
from services.backend.data.models import WalletConfig
from services.backend.core.paper_trading import (
    _ensure_wallet_config,
    get_user_by_wallet,
    get_user_by_telegram,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Trading Mode"], redirect_slashes=False)

# Minimum real USDC balance required to switch to real mode
MIN_REAL_BALANCE_USDC = 10.0


# ─── REQUEST / RESPONSE MODELS ───────────────────────────────────────────────

class ModeToggleRequest(BaseModel):
    wallet_address: Optional[str] = None
    telegram_user_id: Optional[str] = None
    mode: str                         # 'paper' or 'real'
    confirmed: bool = False           # Must be True for paper → real switch


class ModeStatusResponse(BaseModel):
    current_mode: str
    trading_mode: str
    kyc_status: str
    real_balance_usdc: float
    gates: dict                       # Which gates are passed for real mode
    can_switch_to_real: bool


# ─── HELPERS ─────────────────────────────────────────────────────────────────

def _resolve_config(
    wallet_address: Optional[str],
    telegram_user_id: Optional[str],
    session: Session,
) -> WalletConfig:
    """Resolve WalletConfig from wallet_address OR telegram_user_id."""
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


def _build_gates(config: WalletConfig) -> dict:
    """Return which gates are currently passing for real mode."""
    return {
        "kyc_approved":      config.kyc_status == "approved",
        "min_balance_met":   config.real_balance_usdc >= MIN_REAL_BALANCE_USDC,
        "min_balance_usdc":  MIN_REAL_BALANCE_USDC,
        "current_balance":   round(config.real_balance_usdc, 2),
        "kyc_status":        config.kyc_status,
    }


# ─── ENDPOINTS ───────────────────────────────────────────────────────────────

@router.get("/wallet/mode")
def get_mode(
    wallet_address: Optional[str] = None,
    telegram_user_id: Optional[str] = None,
    session: Session = Depends(get_session),
):
    """
    GET /wallet/mode

    Returns the user's current trading mode and the status of each gate.
    The frontend uses this to render the toggle state and show which gates
    are pending (e.g., "You need at least $10 USDC to enable real trading").

    Examples:
        GET /wallet/mode?wallet_address=0xabc...123
        GET /wallet/mode?telegram_user_id=987654321
    """
    config = _resolve_config(wallet_address, telegram_user_id, session)
    gates  = _build_gates(config)

    return {
        "current_mode":      config.trading_mode,
        "trading_mode":      config.trading_mode,
        "kyc_status":        config.kyc_status,
        "real_balance_usdc": round(config.real_balance_usdc, 2),
        "gates":             gates,
        "can_switch_to_real": all([
            gates["kyc_approved"],
            gates["min_balance_met"],
        ]),
    }


@router.post("/wallet/mode")
def set_mode(
    request: ModeToggleRequest,
    session: Session = Depends(get_session),
):
    """
    POST /wallet/mode

    Switch trading mode. The frontend sends:
      { wallet_address, mode: "real", confirmed: true }

    Switching paper → real requires ALL three gates:
      1. kyc_status == "approved"
      2. real_balance_usdc >= 10.0
      3. confirmed == True (user explicitly acknowledged real-money risk)

    Switching real → paper:
      Always allowed, no gates, confirmed not required.

    Returns the updated mode status.
    """
    config = _resolve_config(request.wallet_address, request.telegram_user_id, session)

    requested_mode = request.mode.lower().strip()
    if requested_mode not in ("paper", "real"):
        raise HTTPException(status_code=400, detail="mode must be 'paper' or 'real'.")

    # ── Switching to paper (always allowed) ──────────────────────────────────
    if requested_mode == "paper":
        config.trading_mode = "paper"
        config.updated_at   = __import__("datetime").datetime.utcnow()
        session.add(config)
        session.commit()
        logger.info(f"[mode] {config.telegram_user_id} switched to PAPER mode")
        return {
            "status":       "ok",
            "trading_mode": "paper",
            "message":      "Switched to paper trading mode.",
        }

    # ── Switching to real (three gates enforced) ──────────────────────────────
    gates = _build_gates(config)
    errors = []

    # Gate 1: KYC
    if not gates["kyc_approved"]:
        errors.append(
            f"KYC required. Current status: '{config.kyc_status}'. "
            "Complete identity verification to enable real trading."
        )

    # Gate 2: Minimum balance
    if not gates["min_balance_met"]:
        errors.append(
            f"Minimum balance not met. "
            f"You have ${config.real_balance_usdc:.2f} USDC — "
            f"need at least ${MIN_REAL_BALANCE_USDC:.2f} USDC on Base."
        )

    # Gate 3: Explicit confirmation
    if not request.confirmed:
        errors.append(
            "Explicit confirmation required. "
            "Set confirmed=true to acknowledge this uses real money."
        )

    if errors:
        raise HTTPException(
            status_code=403,
            detail={
                "message":    "Cannot switch to real trading mode.",
                "errors":     errors,
                "gates":      gates,
            },
        )

    # All gates passed — switch to real
    config.trading_mode = "real"
    config.updated_at   = __import__("datetime").datetime.utcnow()
    session.add(config)
    session.commit()

    logger.info(f"[mode] {config.telegram_user_id} switched to REAL mode ✓")
    return {
        "status":       "ok",
        "trading_mode": "real",
        "message":      "Switched to real trading mode. All trades will use real USDC on Base.",
        "gates":        gates,
    }
