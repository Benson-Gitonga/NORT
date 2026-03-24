"""
Bridge API — Phase 2

Endpoints:
  GET  /bridge/quote          → get LI.FI quote (Base → Polygon, USDC)
  POST /bridge/start          → record bridge tx hash, start background polling
  GET  /bridge/status/{id}    → get current status of a bridge transaction
  GET  /bridge/history        → all bridge transactions for a user
  GET  /wallet/real-balance   → cached on-chain USDC balance on Base

These endpoints are only relevant when trading_mode == 'real'.
In paper mode they return immediately with a clear message.
"""

import asyncio
import logging
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlmodel import Session, select

from services.backend.data.database import get_session
from services.backend.data.models import BridgeTransaction, WalletConfig
from services.backend.core.bridge import (
    get_bridge_quote,
    create_bridge_record,
    record_bridge_tx_hash,
    wait_for_bridge,
    BridgeError,
    BridgeRateLimitError,
)
from services.backend.core.paper_trading import (
    _ensure_wallet_config,
    get_user_by_wallet,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/bridge", tags=["Bridge"], redirect_slashes=False)


# ─── MODELS ──────────────────────────────────────────────────────────────────

class QuoteRequest(BaseModel):
    wallet_address: str     # Base wallet (from address)
    amount_usdc: float      # amount to bridge

class StartBridgeRequest(BaseModel):
    wallet_address: str
    telegram_user_id: Optional[str] = None
    amount_usdc: float
    lifi_tx_hash: str       # tx hash returned after user signs + sends

class BridgeStatusRequest(BaseModel):
    bridge_id: int


# ─── HELPERS ─────────────────────────────────────────────────────────────────

def _get_tid(wallet_address: str, telegram_user_id: Optional[str], session: Session) -> str:
    if telegram_user_id:
        return telegram_user_id
    user = get_user_by_wallet(wallet_address.lower(), session)
    return (user.telegram_id or user.wallet_address) if user else wallet_address.lower()


# ─── ENDPOINTS ───────────────────────────────────────────────────────────────

@router.get("/quote")
async def bridge_quote(
    wallet_address: str,
    amount_usdc: float,
    session: Session = Depends(get_session),
):
    """
    GET /bridge/quote?wallet_address=0x...&amount_usdc=50

    Returns a LI.FI quote for bridging USDC from Base → Polygon.
    The quote includes the transactionRequest the frontend must sign.

    Cached for 30 seconds per wallet+amount pair.
    """
    if amount_usdc < 1.0:
        raise HTTPException(status_code=400, detail="Minimum bridge amount is 1 USDC.")

    try:
        quote = await get_bridge_quote(
            from_wallet=wallet_address,
            to_wallet=wallet_address,   # same address on both chains
            amount_usdc=amount_usdc,
        )
        return {
            "status":   "ok",
            "quote":    quote,
            "summary": {
                "from_amount_usdc":  amount_usdc,
                "to_amount_usdc":    float(quote.get("estimate", {}).get("toAmount", 0)) / 1_000_000,
                "bridge_tool":       quote.get("tool", "unknown"),
                "estimated_seconds": quote.get("estimate", {}).get("executionDuration", 120),
                "gas_cost_usd":      quote.get("estimate", {}).get("gasCosts", [{}])[0].get("amountUSD", "~$0.01"),
            }
        }
    except BridgeRateLimitError as e:
        raise HTTPException(status_code=429, detail=str(e))
    except BridgeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/start")
async def start_bridge(
    request: StartBridgeRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
):
    """
    POST /bridge/start

    Called AFTER the user has signed and submitted the bridge transaction
    using Privy on the frontend.

    Body:
      { wallet_address, amount_usdc, lifi_tx_hash }

    Immediately creates a BridgeTransaction record in the DB,
    then starts a background task to poll LI.FI until DONE/FAILED.

    Returns the bridge_id to poll for status updates.
    """
    tid = _get_tid(request.wallet_address, request.telegram_user_id, session)

    # Create DB record
    bridge = create_bridge_record(
        session=session,
        telegram_user_id=tid,
        wallet_address=request.wallet_address,
        amount_usdc=request.amount_usdc,
    )

    # Record the tx hash (user already submitted it)
    record_bridge_tx_hash(session, bridge.id, request.lifi_tx_hash)

    # Start background polling — don't block the API response
    background_tasks.add_task(
        wait_for_bridge,
        tx_hash=request.lifi_tx_hash,
        session=session,
        bridge_id=bridge.id,
    )

    logger.info(f"[bridge] Started bridge {bridge.id} for {tid}: "
                f"{request.amount_usdc} USDC tx={request.lifi_tx_hash[:12]}...")

    return {
        "status":    "bridging",
        "bridge_id": bridge.id,
        "message":   "Bridge started. Poll /bridge/status/{id} for updates.",
        "estimated_minutes": 2,
    }


@router.get("/status/{bridge_id}")
def get_bridge_status_endpoint(
    bridge_id: int,
    session: Session = Depends(get_session),
):
    """
    GET /bridge/status/{bridge_id}

    Returns the current status of a bridge transaction.
    The frontend polls this every 10 seconds to update the progress UI.

    Statuses:
      pending   → tx not yet submitted
      bridging  → tx on Base confirmed, waiting for Polygon
      done      → USDC arrived on Polygon ✓
      failed    → bridge failed
      refunded  → LI.FI refunded back to Base
    """
    bridge = session.get(BridgeTransaction, bridge_id)
    if not bridge:
        raise HTTPException(status_code=404, detail=f"Bridge {bridge_id} not found.")

    return {
        "bridge_id":            bridge.id,
        "status":               bridge.status,
        "amount_usdc":          bridge.amount_usdc,
        "lifi_tx_hash":         bridge.lifi_tx_hash,
        "lifi_receiving_tx_hash": bridge.lifi_receiving_tx_hash,
        "bridge_tool":          bridge.lifi_tool,
        "error_message":        bridge.error_message,
        "created_at":           bridge.created_at.isoformat(),
        "completed_at":         bridge.completed_at.isoformat() if bridge.completed_at else None,
        "elapsed_seconds": int((datetime.utcnow() - bridge.created_at).total_seconds()),
    }


@router.get("/history")
def bridge_history(
    wallet_address: Optional[str] = None,
    telegram_user_id: Optional[str] = None,
    session: Session = Depends(get_session),
):
    """
    GET /bridge/history?wallet_address=0x...

    Returns all bridge transactions for a user, newest first.
    """
    if not wallet_address and not telegram_user_id:
        raise HTTPException(status_code=400, detail="Provide wallet_address or telegram_user_id.")

    tid = telegram_user_id
    if wallet_address and not telegram_user_id:
        user = get_user_by_wallet(wallet_address.lower(), session)
        tid  = (user.telegram_id or user.wallet_address) if user else wallet_address.lower()

    bridges = session.exec(
        select(BridgeTransaction)
        .where(BridgeTransaction.telegram_user_id == str(tid))
        .order_by(BridgeTransaction.created_at.desc())
    ).all()

    return {
        "total": len(bridges),
        "bridges": [
            {
                "id":           b.id,
                "status":       b.status,
                "amount_usdc":  b.amount_usdc,
                "from_chain":   b.from_chain,
                "to_chain":     b.to_chain,
                "tx_hash":      b.lifi_tx_hash,
                "created_at":   b.created_at.isoformat(),
                "completed_at": b.completed_at.isoformat() if b.completed_at else None,
            }
            for b in bridges
        ]
    }
