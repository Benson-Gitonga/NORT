"""
Leaderboard, User Stats, and Achievements API routes for NORT.

Endpoints
─────────
  GET /leaderboard                  — Full ranked board
  GET /leaderboard/me               — Personal rank card
  GET /user/stats                   — XP / level / streak
  GET /user/achievements            — Earned + locked achievements

Both /leaderboard and /leaderboard/me accept ?mode=paper|real
  mode=paper → ranks by paper portfolio value (default)
  mode=real  → ranks by real USDC balance from RealTrade table
"""

from typing import Optional, Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from services.backend.data.database import get_session
from services.backend.core.leaderboard import (
    get_leaderboard,
    get_user_rank,
    get_user_stats,
    get_achievements,
)

router = APIRouter(tags=["Leaderboard"], redirect_slashes=False)


def _resolve_tid(
    telegram_user_id: Optional[str],
    wallet_address: Optional[str],
) -> str:
    if telegram_user_id:
        return telegram_user_id
    if wallet_address:
        return wallet_address.lower()
    return None


# ─── GET /leaderboard ────────────────────────────────────────────────────────

@router.get("/leaderboard")
def leaderboard(
    limit: int = Query(default=50, le=200),
    mode: str = Query(default="paper", description="'paper' or 'real'"),
    session: Session = Depends(get_session),
):
    """
    Returns the full ranked leaderboard.

    ?mode=paper  → ranked by paper portfolio value (default, existing behaviour)
    ?mode=real   → ranked by real USDC balance + real trade P&L

    Example: GET /leaderboard?mode=real&limit=20
    """
    if mode not in ("paper", "real"):
        raise HTTPException(status_code=400, detail="mode must be 'paper' or 'real'.")
    try:
        board = get_leaderboard(session=session, limit=limit, mode=mode)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "mode":          mode,
        "total_players": len(board),
        "leaderboard":   board,
    }


# ─── GET /leaderboard/me ─────────────────────────────────────────────────────

@router.get("/leaderboard/me")
def my_rank(
    telegram_user_id: Optional[str] = None,
    wallet_address: Optional[str] = None,
    mode: str = Query(default="paper"),
    session: Session = Depends(get_session),
):
    """
    Returns a single user's leaderboard entry including rank, badge, XP, streak.

    ?mode=paper|real  → which leaderboard to look up rank from

    Examples:
        GET /leaderboard/me?wallet_address=0xabc...123
        GET /leaderboard/me?wallet_address=0xabc...123&mode=real
    """
    tid = _resolve_tid(telegram_user_id, wallet_address)
    if not tid:
        raise HTTPException(status_code=400, detail="Provide telegram_user_id or wallet_address.")
    if mode not in ("paper", "real"):
        raise HTTPException(status_code=400, detail="mode must be 'paper' or 'real'.")

    try:
        entry = get_user_rank(tid, session, mode=mode)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if not entry:
        raise HTTPException(status_code=404, detail="User not found on leaderboard.")

    return entry


# ─── GET /user/stats ─────────────────────────────────────────────────────────

@router.get("/user/stats")
def user_stats(
    telegram_user_id: Optional[str] = None,
    wallet_address: Optional[str] = None,
    session: Session = Depends(get_session),
):
    tid = _resolve_tid(telegram_user_id, wallet_address)
    if not tid:
        raise HTTPException(status_code=400, detail="Provide telegram_user_id or wallet_address.")
    try:
        stats = get_user_stats(tid, session)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return stats


# ─── GET /user/achievements ───────────────────────────────────────────────────

@router.get("/user/achievements")
def user_achievements(
    telegram_user_id: Optional[str] = None,
    wallet_address: Optional[str] = None,
    session: Session = Depends(get_session),
):
    tid = _resolve_tid(telegram_user_id, wallet_address)
    if not tid:
        raise HTTPException(status_code=400, detail="Provide telegram_user_id or wallet_address.")
    try:
        achievements = get_achievements(tid, session)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    earned_count = sum(1 for a in achievements if a["earned"])
    total_xp     = sum(a["xp"] for a in achievements if a["earned"])

    return {
        "total":        len(achievements),
        "earned_count": earned_count,
        "total_xp":     total_xp,
        "achievements": achievements,
    }
