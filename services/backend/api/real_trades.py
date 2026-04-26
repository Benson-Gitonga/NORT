"""
Real Trading API Routes — Phase 4

Endpoints:
  POST /real/trade             — Place a real on-chain trade on Polymarket CLOB
  GET  /real/trades            — List the user's real trades
  GET  /real/trade/{id}        — Single real trade detail
  POST /real/settle            — Manually trigger settlement check for open trades
  GET  /wallet/server-balance  — Server wallet's live USDC balance on Polygon (operator view)

All endpoints require Privy auth (Authorization: Bearer <token>).
The real trade path additionally requires:
  - trading_mode == 'real' in WalletConfig
  - REAL_TRADING_ENABLED == "true" in env
  - Wallet address in REAL_TRADING_BETA_ALLOWLIST (if set)
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlmodel import Session, select

from services.backend.api.auth import get_current_user
from services.backend.data.database import get_session
from services.backend.data.models import RealTrade, WalletConfig
from services.backend.core.real_trading_engine import (
    place_real_trade,
    settle_open_real_trades,
    get_server_wallet_usdc_balance,
    RealTradingError,
    RealTradingDisabledError,
    InsufficientRealBalanceError,
    PolymarketError,
    ConfigurationError,
    MIN_REAL_TRADE_USDC,
    MAX_REAL_TRADE_USDC,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Real Trading"], redirect_slashes=False)


# ─── REQUEST / RESPONSE MODELS ────────────────────────────────────────────────

class RealTradeRequest(BaseModel):
    market_id:       str
    market_question: str
    outcome:         str    # "YES" or "NO"
    amount_usdc:     float  # USDC to spend

    @field_validator("outcome")
    @classmethod
    def validate_outcome(cls, v: str) -> str:
        normalized = v.strip().upper()
        if normalized not in ("YES", "NO"):
            raise ValueError("outcome must be 'YES' or 'NO'")
        return normalized

    @field_validator("amount_usdc")
    @classmethod
    def validate_amount(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("amount_usdc must be greater than 0")
        return round(v, 6)

    @field_validator("market_id")
    @classmethod
    def validate_market_id(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("market_id cannot be empty")
        return v


# ─── HELPERS ─────────────────────────────────────────────────────────────────

def _require_real_mode(current_user: dict, session: Session) -> WalletConfig:
    """
    Verify the user is in real trading mode.
    Returns the WalletConfig if ok, raises 403 otherwise.
    """
    wallet = current_user["wallet"].lower()
    config = session.exec(
        select(WalletConfig).where(WalletConfig.telegram_user_id == wallet)
    ).first()

    if not config:
        raise HTTPException(
            status_code=403,
            detail="No wallet config found. Connect your wallet first."
        )

    if config.trading_mode != "real":
        raise HTTPException(
            status_code=403,
            detail={
                "error":   "not_in_real_mode",
                "message": "Switch to real trading mode before placing real trades.",
                "hint":    "POST /wallet/mode with mode='real' and confirmed=true",
            }
        )
    return config


def _real_trade_to_dict(t: RealTrade) -> dict:
    pnl_display = None
    if t.pnl is not None:
        pnl_display = f"+${t.pnl:.2f}" if t.pnl >= 0 else f"-${abs(t.pnl):.2f}"

    return {
        "id":                   t.id,
        "market_id":            t.market_id,
        "market_question":      t.market_question,
        "outcome":              t.outcome,
        "shares":               t.shares,
        "price_per_share":      t.price_per_share,
        "total_cost_usdc":      t.total_cost_usdc,
        "polymarket_order_id":  t.polymarket_order_id,
        "polygon_tx_hash":      t.polygon_tx_hash,
        "status":               t.status,
        "pnl":                  t.pnl,
        "pnl_display":          pnl_display,
        "result":               "WIN" if (t.pnl or 0) > 0 else "LOSS" if (t.pnl or 0) < 0 else t.status.upper(),
        "settled_at":           t.settled_at.isoformat() if t.settled_at else None,
        "created_at":           t.created_at.isoformat(),
        "updated_at":           t.updated_at.isoformat(),
        "error_message":        t.error_message,
    }


# ─── PLACE REAL TRADE ─────────────────────────────────────────────────────────

@router.post("/real/trade")
async def create_real_trade(
    request: RealTradeRequest,
    session:      Session = Depends(get_session),
    current_user: dict    = Depends(get_current_user),
):
    """
    POST /real/trade

    Place a real on-chain trade on Polymarket CLOB via the server wallet.

    Requirements:
      - User must be authenticated (Privy JWT in Authorization header)
      - User must be in real trading mode (POST /wallet/mode first)
      - REAL_TRADING_ENABLED=true in env
      - User must have sufficient real_balance_usdc

    The trade is a Fill-or-Kill (FOK) market order — it either fills
    completely at or better than the current market price, or is cancelled.
    If cancelled, your balance is refunded immediately.

    Body:
      {
        "market_id":       "0x...",
        "market_question": "Will BTC hit $100k by June?",
        "outcome":         "YES",
        "amount_usdc":     10.0
      }
    """
    wallet = current_user["wallet"].lower()

    # Verify real mode
    _require_real_mode(current_user, session)

    logger.info(
        f"[api/real_trade] Incoming: wallet={wallet[:10]} "
        f"market={request.market_id[:12]} outcome={request.outcome} "
        f"amount={request.amount_usdc}"
    )

    try:
        trade = await place_real_trade(
            telegram_user_id=wallet,
            wallet_address=wallet,
            market_id=request.market_id,
            market_question=request.market_question,
            outcome=request.outcome,
            amount_usdc=request.amount_usdc,
            session=session,
        )
    except RealTradingDisabledError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except InsufficientRealBalanceError as e:
        raise HTTPException(status_code=402, detail=str(e))
    except ConfigurationError as e:
        logger.error(f"[api/real_trade] Config error: {e}")
        raise HTTPException(status_code=503, detail=str(e))
    except PolymarketError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except RealTradingError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"[api/real_trade] Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")

    return {
        "status":        "ok",
        "message":       f"Real trade placed: {request.outcome} on '{request.market_question}'",
        "trade":         _real_trade_to_dict(trade),
        "note":          (
            "Your trade is now open on Polymarket. "
            "It will auto-settle when the market resolves. "
            "Check /real/trades for current status."
        ),
    }


# ─── LIST REAL TRADES ─────────────────────────────────────────────────────────

@router.get("/real/trades")
def list_real_trades(
    status:       Optional[str] = None,   # filter: open | closed | failed | pending_execution
    limit:        int           = 50,
    session:      Session       = Depends(get_session),
    current_user: dict          = Depends(get_current_user),
):
    """
    GET /real/trades

    Returns all real trades for the authenticated user.
    Optionally filter by status: open | closed | failed | pending_execution

    Example:
      GET /real/trades
      GET /real/trades?status=open
      GET /real/trades?status=closed&limit=10
    """
    wallet = current_user["wallet"].lower()

    stmt = select(RealTrade).where(RealTrade.telegram_user_id == wallet)
    if status:
        stmt = stmt.where(RealTrade.status == status.lower())
    stmt = stmt.order_by(RealTrade.created_at.desc()).limit(limit)

    trades = session.exec(stmt).all()

    # Compute summary stats
    closed  = [t for t in trades if t.status == "closed" and t.pnl is not None]
    wins    = [t for t in closed if (t.pnl or 0) > 0]
    losses  = [t for t in closed if (t.pnl or 0) <= 0]
    net_pnl = round(sum(t.pnl for t in closed), 2)

    return {
        "count":    len(trades),
        "summary": {
            "open":     len([t for t in trades if t.status == "open"]),
            "closed":   len(closed),
            "wins":     len(wins),
            "losses":   len(losses),
            "net_pnl":  net_pnl,
        },
        "trades": [_real_trade_to_dict(t) for t in trades],
    }


# ─── SINGLE REAL TRADE ───────────────────────────────────────────────────────

@router.get("/real/trade/{trade_id}")
def get_real_trade(
    trade_id:     int,
    session:      Session = Depends(get_session),
    current_user: dict    = Depends(get_current_user),
):
    """
    GET /real/trade/{trade_id}

    Returns full detail for a single real trade.
    Returns 404 if not found, 403 if it belongs to another user.
    """
    wallet = current_user["wallet"].lower()
    trade  = session.get(RealTrade, trade_id)

    if not trade:
        raise HTTPException(status_code=404, detail=f"Trade {trade_id} not found.")
    if trade.telegram_user_id.lower() != wallet:
        raise HTTPException(status_code=403, detail="Not your trade.")

    return _real_trade_to_dict(trade)


# ─── MANUAL SETTLEMENT TRIGGER ────────────────────────────────────────────────

@router.post("/real/settle")
async def trigger_settlement(
    session:      Session = Depends(get_session),
    current_user: dict    = Depends(get_current_user),
):
    """
    POST /real/settle

    Manually trigger settlement checks for the authenticated user's open trades.
    Normally this runs as a background job every few minutes — this endpoint
    lets users check immediately if they think a market has resolved.

    For each open trade:
      - Fetches the market from Polymarket CLOB
      - If resolved → credits payout to real_balance_usdc, closes trade
      - If still open → skips

    Returns a list of trades that were settled.
    """
    wallet = current_user["wallet"].lower()

    # Only settle this user's trades (not global settle)
    open_trades = session.exec(
        select(RealTrade).where(
            RealTrade.telegram_user_id == wallet,
            RealTrade.status == "open",
        )
    ).all()

    if not open_trades:
        return {
            "settled": 0,
            "message": "No open real trades to settle.",
            "results": [],
        }

    # Run settlement check for just this user's trades
    from services.backend.core.real_trading_engine import _settle_single_trade
    results = []
    for trade in open_trades:
        try:
            result = await _settle_single_trade(trade, session)
            if result:
                results.append(result)
        except Exception as e:
            logger.error(f"[settle] Trade {trade.id} error: {e}")

    return {
        "settled":  len(results),
        "checked":  len(open_trades),
        "message":  f"Settled {len(results)} of {len(open_trades)} open trades.",
        "results":  results,
    }


# ─── SERVER WALLET BALANCE (OPERATOR) ────────────────────────────────────────

@router.get("/wallet/server-balance")
async def server_wallet_balance(
    current_user: dict = Depends(get_current_user),
):
    """
    GET /wallet/server-balance

    Returns the server wallet's live USDC balance on Polygon.
    This is the custodial pool that backs all real trades.

    Useful for operators to verify the server wallet is adequately funded
    before enabling real trading for users.

    Note: This queries the Polygon RPC directly — it shows the true on-chain
    balance, not a DB-computed value.
    """
    balance = await get_server_wallet_usdc_balance()

    return {
        "server_wallet_address": os.getenv("SERVER_POLYGON_WALLET_ADDRESS", "not configured"),
        "usdc_balance_polygon":  balance,
        "chain":                 "Polygon",
        "usdc_contract":         "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359",
        "note": (
            "This is the custodial server wallet backing all real trades. "
            "Ensure this balance is sufficient to cover all open positions."
        ),
    }


import os