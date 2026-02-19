"""
Paper trading routes for Polymarket AI Assistant.
Intern 5 - Paper Trading

Endpoints:
  POST /papertrade      — Place a paper trade
  POST /trade/commit    — Optional Polygon testnet receipt
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from services.backend.data.database import get_session
from services.backend.core.paper_trading import place_paper_trade, commit_trade_to_testnet

router = APIRouter(tags=["Paper Trading"])


class PaperTradeRequest(BaseModel):
    telegram_user_id: str   # Must be linked to a wallet via /wallet/connect first
    market_id: str          # Polymarket market ID (from Intern 1's /markets)
    market_question: str    # e.g. "Will ETH hit $5k by Friday?"
    outcome: str            # "YES" or "NO"
    shares: float           # Number of shares to buy e.g. 100
    price_per_share: float  # Current market price e.g. 0.65
    direction: str          # "BUY" or "SELL"


class CommitTradeRequest(BaseModel):
    trade_id: int


@router.post("/papertrade")
def create_paper_trade(
    request: PaperTradeRequest,
    session: Session = Depends(get_session)
):
    """
    Place a paper trade. No real USDC moves — simulation only.

    Requirements:
    - telegram_user_id must have a linked wallet (POST /wallet/connect first)
    - outcome: YES or NO
    - direction: BUY or SELL
    - price_per_share: between 0 and 1
    - shares x price must be >= 1 paper USDC
    - Sufficient paper balance for BUY trades

    Example:
        {
          "telegram_user_id": "987654321",
          "market_id": "eth-5k-friday",
          "market_question": "Will ETH hit $5k by Friday?",
          "outcome": "YES",
          "shares": 100,
          "price_per_share": 0.65,
          "direction": "BUY"
        }
    """
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


@router.post("/trade/commit")
def commit_trade(
    request: CommitTradeRequest,
    session: Session = Depends(get_session)
):
    """
    Attach a Polygon TESTNET receipt to a paper trade.
    No real money moves — mock tx hash for demo purposes.

    Example:
        { "trade_id": 1 }
    """
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