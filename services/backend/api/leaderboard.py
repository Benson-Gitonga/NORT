"""
Leaderboard API routes for NORT.

Endpoints:
  GET /leaderboard          — Full ranked leaderboard (top 50)
  GET /leaderboard/me       — Your rank + stats
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from services.backend.data.database import get_session
from services.backend.core.leaderboard import get_leaderboard, get_user_rank

router = APIRouter(tags=["Leaderboard"])


@router.get("/leaderboard")
def leaderboard(
    limit: int = Query(default=50, le=100),
    session: Session = Depends(get_session),
):
    """
    Returns ranked list of all paper traders sorted by portfolio value.
    Includes badges, XP, win rate, streak.

    Example: GET /leaderboard?limit=20
    """
    try:
        board = get_leaderboard(session=session, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "total_players": len(board),
        "leaderboard": board,
    }


@router.get("/leaderboard/me")
def my_rank(
    telegram_user_id: Optional[str] = None,
    wallet_address: Optional[str] = None,
    session: Session = Depends(get_session),
):
    """
    Get your personal rank, badge, XP and stats.

    Example:
        GET /leaderboard/me?telegram_user_id=987654321
        GET /leaderboard/me?wallet_address=0xABC...123
    """
    if not telegram_user_id and not wallet_address:
        raise HTTPException(
            status_code=400,
            detail="Provide telegram_user_id or wallet_address."
        )

    tid = telegram_user_id or wallet_address.lower()

    try:
        entry = get_user_rank(tid, session)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if not entry:
        raise HTTPException(status_code=404, detail="User not found on leaderboard.")

    return entry
