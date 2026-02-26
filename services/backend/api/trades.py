"""
Paper trading routes for NORT.

Endpoints:
  POST /papertrade              — Buy a position
  POST /trade/sell/{id}         — Sell a position at current market price  ← NEW
  GET  /trade/value/{id}        — Get live mark-to-market value            ← NEW
  POST /trade/settle/{id}       — Auto-settle if market resolved
  POST /trade/settle-all        — Settle all open trades
  GET  /trade/history           — Full trade history
  POST /trade/commit            — Testnet receipt (cosmetic)
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select
from typing import Optional

from services.backend.data.database import get_session
from services.backend.data.models import PaperTrade
from services.backend.core.paper_trading import (
    place_paper_trade,
    sell_trade,
    get_position_value,
    commit_trade_to_testnet,
    settle_trade,
    settle_all_open_trades,
)

router = APIRouter(tags=["Paper Trading"], redirect_slashes=False)


class PaperTradeRequest(BaseModel):
    telegram_user_id: str
    market_id: str
    market_question: str
    outcome: str        # "YES" or "NO"
    shares: float
    price_per_share: float
    direction: str      # "BUY" or "SELL"


class CommitTradeRequest(BaseModel):
    trade_id: int


class SettleAllRequest(BaseModel):
    telegram_user_id: str


# ─── BUY ─────────────────────────────────────────────────────────────────────

@router.post("/papertrade")
def create_paper_trade(request: PaperTradeRequest, session: Session = Depends(get_session)):
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
        "status":          "trade_placed",
        "trade_id":        trade.id,
        "telegram_user_id": trade.telegram_user_id,
        "market_question": trade.market_question,
        "outcome":         trade.outcome,
        "direction":       trade.direction,
        "shares":          trade.shares,
        "price_per_share": trade.price_per_share,
        "total_cost":      trade.total_cost,
        "trade_status":    trade.status,
        "created_at":      trade.created_at.isoformat(),
        "note":            "Paper trade only. No real USDC was spent.",
    }


# ─── SELL (exit early at current market price) ───────────────────────────────

@router.post("/trade/sell/{trade_id}")
def sell_position(trade_id: int, session: Session = Depends(get_session)):
    """
    Sell an open position at the current live market price.

    Mirrors Polymarket: you can exit any time before resolution.
    Payout = shares × current_price
    P&L    = payout − original_cost

    Example: POST /trade/sell/42
    """
    try:
        result = sell_trade(trade_id, session)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return result


# ─── LIVE POSITION VALUE ─────────────────────────────────────────────────────

@router.get("/trade/value/{trade_id}")
def position_value(trade_id: int, session: Session = Depends(get_session)):
    """
    Get the current mark-to-market value of an open position.
    Used by the frontend sell modal to show what you'd receive right now.

    Example: GET /trade/value/42
    """
    try:
        result = get_position_value(trade_id, session)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return result


# ─── SETTLE (auto, on market resolution) ─────────────────────────────────────

@router.post("/trade/settle/{trade_id}")
def settle_one_trade(trade_id: int, session: Session = Depends(get_session)):
    try:
        result = settle_trade(trade_id, session)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return result


@router.post("/trade/settle-all")
def settle_all_trades(request: SettleAllRequest, session: Session = Depends(get_session)):
    try:
        results = settle_all_open_trades(request.telegram_user_id, session)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    settled    = [r for r in results if r["status"] == "CLOSED"]
    still_open = [r for r in results if r["status"] == "OPEN"]
    return {
        "total_checked": len(results),
        "settled":       len(settled),
        "still_open":    len(still_open),
        "results":       results,
    }


# ─── TRADE HISTORY ───────────────────────────────────────────────────────────

@router.get("/trade/history")
def trade_history(
    telegram_user_id: str,
    status: Optional[str] = None,
    session: Session = Depends(get_session),
):
    stmt = select(PaperTrade).where(PaperTrade.telegram_user_id == str(telegram_user_id))
    if status:
        stmt = stmt.where(PaperTrade.status == status.upper())
    stmt = stmt.order_by(PaperTrade.created_at.desc())
    trades = session.exec(stmt).all()

    def label(t):
        if t.status != "CLOSED":
            return "OPEN"
        if (t.pnl or 0) > 0:
            return "WIN"
        if (t.pnl or 0) < 0:
            return "LOSS"
        return "BREAK_EVEN"

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
                "result":          label(t),
                "pnl":             t.pnl,
                "pnl_display":     (f"+${t.pnl:.2f}" if (t.pnl or 0) >= 0
                                    else f"-${abs(t.pnl):.2f}") if t.pnl is not None else None,
                "closed_at":       t.closed_at.isoformat() if t.closed_at else None,
                "created_at":      t.created_at.isoformat(),
            }
            for t in trades
        ],
    }


# ─── TESTNET COMMIT ──────────────────────────────────────────────────────────

@router.post("/trade/commit")
def commit_trade(request: CommitTradeRequest, session: Session = Depends(get_session)):
    try:
        tx_hash = commit_trade_to_testnet(request.trade_id, session)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {
        "status":   "committed",
        "trade_id": request.trade_id,
        "tx_hash":  tx_hash,
        "network":  "Polygon Mumbai Testnet",
        "note":     "Testnet receipt only. No real value.",
    }
