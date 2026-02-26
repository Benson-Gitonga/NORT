"""
Paper trading routes for Polymarket AI Assistant.
Intern 5 - Paper Trading

Endpoints:
  POST /papertrade           — Place a paper trade
  POST /trade/commit         — Optional Polygon testnet receipt
  POST /trade/settle/{id}    — Settle one trade, calculate WIN/LOSS + P&L
  POST /trade/settle-all     — Settle all open trades for a user
  GET  /trade/history        — Full trade history with results
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select
from typing import Optional

from services.backend.data.database import get_session
from services.backend.data.models import PaperTrade
from services.backend.core.paper_trading import (
    place_paper_trade,
    commit_trade_to_testnet,
    settle_trade,
    settle_all_open_trades,
)

router = APIRouter(tags=["Paper Trading"], redirect_slashes=False)


class PaperTradeRequest(BaseModel):
    telegram_user_id: str
    market_id: str
    market_question: str
    outcome: str            # "YES" or "NO"
    shares: float
    price_per_share: float
    direction: str          # "BUY" or "SELL"


class CommitTradeRequest(BaseModel):
    trade_id: int


class SettleAllRequest(BaseModel):
    telegram_user_id: str


# ─────────────────────────────────────────────
# PLACE A TRADE
# ─────────────────────────────────────────────

@router.post("/papertrade")
def create_paper_trade(
    request: PaperTradeRequest,
    session: Session = Depends(get_session)
):
    try:
        trade = place_paper_trade(
            telegram_user_id=request.telegram_user_id,
            market_id=request.market_id,
            market_question=request.market_question,
            outcome=request.outcome,
            shares=request.shares,
            price_per_share=request.price_per_share,
            direction=request.direction,
            session=session,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "status": "trade_placed",
        "trade_id": trade.id,
        "telegram_user_id": trade.telegram_user_id,
        "market_question": trade.market_question,
        "outcome": trade.outcome,
        "direction": trade.direction,
        "shares": trade.shares,
        "price_per_share": trade.price_per_share,
        "total_cost": trade.total_cost,
        "trade_status": trade.status,
        "created_at": trade.created_at.isoformat(),
        "note": "Paper trade only. No real USDC was spent.",
    }


# ─────────────────────────────────────────────
# SETTLE ONE TRADE — checks Polymarket, calculates WIN/LOSS
# ─────────────────────────────────────────────

@router.post("/trade/settle/{trade_id}")
def settle_one_trade(
    trade_id: int,
    session: Session = Depends(get_session)
):
    """
    Check if a market resolved and settle the trade.

    - WIN:  your outcome matches the resolved outcome → payout = shares × $1.00
    - LOSS: wrong outcome → payout = $0, P&L = -total_cost
    - OPEN: market hasn't resolved yet → no change

    Example: POST /trade/settle/42
    """
    try:
        result = settle_trade(trade_id, session)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return result


# ─────────────────────────────────────────────
# SETTLE ALL OPEN TRADES FOR A USER
# ─────────────────────────────────────────────

@router.post("/trade/settle-all")
def settle_all_trades(
    request: SettleAllRequest,
    session: Session = Depends(get_session)
):
    """
    Attempt to settle every open trade for a user.
    Markets that haven't resolved yet are left OPEN.

    Example: POST /trade/settle-all
    { "telegram_user_id": "987654321" }
    """
    try:
        results = settle_all_open_trades(request.telegram_user_id, session)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    settled   = [r for r in results if r["status"] == "CLOSED"]
    still_open = [r for r in results if r["status"] == "OPEN"]

    return {
        "total_checked": len(results),
        "settled": len(settled),
        "still_open": len(still_open),
        "results": results,
    }


# ─────────────────────────────────────────────
# TRADE HISTORY WITH RESULTS
# ─────────────────────────────────────────────

@router.get("/trade/history")
def trade_history(
    telegram_user_id: str,
    status: Optional[str] = None,   # "OPEN", "CLOSED", or omit for all
    session: Session = Depends(get_session)
):
    """
    Full trade history for a user with WIN/LOSS results.

    Examples:
        GET /trade/history?telegram_user_id=987654321
        GET /trade/history?telegram_user_id=987654321&status=CLOSED
    """
    stmt = select(PaperTrade).where(PaperTrade.telegram_user_id == str(telegram_user_id))
    if status:
        stmt = stmt.where(PaperTrade.status == status.upper())
    stmt = stmt.order_by(PaperTrade.created_at.desc())

    trades = session.exec(stmt).all()

    return {
        "telegram_user_id": telegram_user_id,
        "count": len(trades),
        "trades": [
            {
                "id":              t.id,
                "market_id":       t.market_id,
                "market_question": t.market_question,
                "outcome":         t.outcome,
                "direction":       t.direction,
                "shares":          t.shares,
                "price_per_share": t.price_per_share,
                "total_cost":      t.total_cost,
                "status":          t.status,
                "result":          ("WIN" if (t.pnl or 0) > 0 else "LOSS") if t.status == "CLOSED" else "OPEN",
                "pnl":             t.pnl,
                "pnl_display":     f"+${t.pnl:.2f}" if (t.pnl or 0) > 0 else (f"-${abs(t.pnl):.2f}" if t.pnl else None),
                "closed_at":       t.closed_at.isoformat() if t.closed_at else None,
                "created_at":      t.created_at.isoformat(),
            }
            for t in trades
        ],
    }


# ─────────────────────────────────────────────
# TESTNET COMMIT
# ─────────────────────────────────────────────

@router.post("/trade/commit")
def commit_trade(
    request: CommitTradeRequest,
    session: Session = Depends(get_session)
):
    try:
        tx_hash = commit_trade_to_testnet(request.trade_id, session)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "status": "committed",
        "trade_id": request.trade_id,
        "tx_hash": tx_hash,
        "network": "Polygon Mumbai Testnet",
        "note": "Testnet receipt only. No real value.",
    }
