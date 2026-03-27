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
from services.backend.data.models import PaperTrade, PendingTrade
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


# ─── TASK 11: CONFIRM PENDING TRADE ─────────────────────────────────────────

class ConfirmTradeRequest(BaseModel):
    telegram_user_id: str
    action: str   # "yes" | "no"


@router.post("/trade/confirm/{pending_id}")
def confirm_pending_trade(
    pending_id: int,
    request: ConfirmTradeRequest,
    session: Session = Depends(get_session),
):
    """
    Called by the Telegram bot when the user replies YES or NO
    to a confirmation prompt created by AutoTradeEngine in 'confirm' mode.

    YES → validates expiry, fires a paper trade, marks PendingTrade confirmed
    NO  → marks PendingTrade cancelled, no trade is placed
    """
    from datetime import timezone
    from services.backend.core.paper_trading import place_paper_trade

    pending = session.get(PendingTrade, pending_id)
    if not pending:
        raise HTTPException(status_code=404, detail=f"PendingTrade {pending_id} not found.")

    if pending.telegram_user_id != request.telegram_user_id:
        raise HTTPException(status_code=403, detail="This confirmation does not belong to you.")

    if pending.status != "pending":
        raise HTTPException(
            status_code=409,
            detail=f"PendingTrade {pending_id} is already {pending.status}."
        )

    # Check expiry
    now = datetime.utcnow().replace(tzinfo=timezone.utc)
    expires = pending.expires_at.replace(tzinfo=timezone.utc) if pending.expires_at.tzinfo is None \
              else pending.expires_at
    if now > expires:
        pending.status = "expired"
        session.add(pending)
        session.commit()
        raise HTTPException(status_code=410, detail="Confirmation window expired (10 minutes). No trade placed.")

    if request.action.lower() == "no":
        pending.status = "cancelled"
        session.add(pending)
        session.commit()
        return {"status": "cancelled", "message": "Trade cancelled. No position was opened."}

    if request.action.lower() != "yes":
        raise HTTPException(status_code=400, detail="action must be 'yes' or 'no'.")

    # Fire the paper trade
    outcome = "YES" if "YES" in pending.suggested_plan.upper() else "NO"
    price   = pending.amount_usdc / 10  # derive shares: $amount at $0.10/share default
    shares  = round(pending.amount_usdc / 0.65, 4)   # use mid-market price as estimate

    try:
        trade = place_paper_trade(
            telegram_user_id=pending.telegram_user_id,
            market_id=pending.market_id,
            market_question=pending.market_question,
            outcome=outcome,
            shares=shares,
            price_per_share=round(pending.amount_usdc / shares, 6),
            direction="BUY",
            session=session,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    pending.status       = "confirmed"
    pending.confirmed_at = datetime.utcnow()
    session.add(pending)
    session.commit()

    return {
        "status":        "confirmed",
        "pending_id":    pending_id,
        "trade_id":      trade.id,
        "market_id":     trade.market_id,
        "outcome":       trade.outcome,
        "shares":        trade.shares,
        "total_cost":    trade.total_cost,
        "message":       f"Trade confirmed and placed. BUY {outcome} on {pending.market_id} for ${trade.total_cost:.2f} USDC.",
    }


# ─── TASK 11: CONFIRM A PENDING TRADE ───────────────────────────────────────

class ConfirmTradeRequest(BaseModel):
    telegram_user_id: str
    action: str   # "YES" to execute, "NO" to cancel


@router.post("/trade/confirm/{pending_id}")
def confirm_pending_trade(
    pending_id: int,
    request: ConfirmTradeRequest,
    session: Session = Depends(get_session),
):
    """
    Called by the Telegram bot when a user replies YES or NO to a
    confirmation prompt generated by AutoTradeEngine in 'confirm' mode.

    YES → executes the trade as a paper trade and closes the pending record.
    NO  → cancels the pending record, no trade fired.
    Expired records (> 10 min) are rejected regardless of action.
    """
    from datetime import timezone
    from services.backend.core.paper_trading import place_paper_trade

    pending = session.get(PendingTrade, pending_id)
    if not pending:
        raise HTTPException(status_code=404, detail=f"PendingTrade {pending_id} not found.")

    if pending.telegram_user_id != request.telegram_user_id:
        raise HTTPException(status_code=403, detail="This pending trade belongs to a different user.")

    if pending.status != "pending":
        raise HTTPException(
            status_code=409,
            detail=f"PendingTrade {pending_id} is already {pending.status}."
        )

    # Check expiry
    now = datetime.utcnow()
    expires = pending.expires_at
    if expires.tzinfo is not None:
        expires = expires.replace(tzinfo=None)
    if now > expires:
        pending.status = "expired"
        session.add(pending)
        session.commit()
        raise HTTPException(status_code=410, detail="Confirmation window expired (10 min). No trade was placed.")

    if request.action.upper() == "NO":
        pending.status = "cancelled"
        session.add(pending)
        session.commit()
        return {"status": "cancelled", "message": "Trade cancelled. No position was opened."}

    if request.action.upper() != "YES":
        raise HTTPException(status_code=400, detail="action must be 'YES' or 'NO'.")

    # Execute as a paper trade
    outcome = "YES" if "YES" in pending.suggested_plan else "NO"
    shares = round(pending.amount_usdc / 0.50, 4)   # normalised entry price of 0.50

    try:
        trade = place_paper_trade(
            telegram_user_id=pending.telegram_user_id,
            market_id=pending.market_id,
            market_question=pending.market_question,
            outcome=outcome,
            shares=shares,
            price_per_share=0.50,
            direction="BUY",
            session=session,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    pending.status       = "confirmed"
    pending.confirmed_at = datetime.utcnow()
    session.add(pending)
    session.commit()

    return {
        "status":          "confirmed",
        "pending_trade_id": pending_id,
        "trade_id":        trade.id,
        "market_id":       pending.market_id,
        "outcome":         outcome,
        "shares":          shares,
        "amount_usdc":     pending.amount_usdc,
        "message":         f"Trade executed: BUY {outcome} on {pending.market_id} for ${pending.amount_usdc} USDC.",
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
