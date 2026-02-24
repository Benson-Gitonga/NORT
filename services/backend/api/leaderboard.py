"""
Leaderboard, User Stats, and Achievements API routes for NORT.

Endpoints
─────────
  GET /leaderboard                  — Full ranked board (portfolio value desc)
  GET /leaderboard/me               — Personal rank card
  GET /user/stats                   — XP / level / streak for achievements header
  GET /user/achievements            — Earned + locked achievement list
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from services.backend.data.database import get_session
from services.backend.core.leaderboard import (
    get_leaderboard,
    get_user_rank,
    get_user_stats,
    get_achievements,
)

router = APIRouter(tags=["Leaderboard"])


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def _resolve_tid(
    telegram_user_id: Optional[str],
    wallet_address: Optional[str],
) -> str:
    """
    Both pages (leaderboard & achievements) identify a user by wallet_address
    (how the dashboard stores it) or telegram_user_id (how the bot stores it).
    The paper-trading core uses telegram_user_id as the primary key.
    When only wallet_address is given we treat it as the tid — the paper_trading
    layer falls back the same way when a wallet hasn't been Telegram-linked yet.
    """
    if telegram_user_id:
        return telegram_user_id
    if wallet_address:
        return wallet_address.lower()
    return None


# ─────────────────────────────────────────────
# GET /leaderboard
# ─────────────────────────────────────────────

@router.get("/leaderboard")
def leaderboard(
    limit: int = Query(default=50, le=200),
    session: Session = Depends(get_session),
):
    """
    Returns the full ranked leaderboard sorted by portfolio value.

    Each entry includes:
      rank, display_name, portfolio_value, net_pnl, net_pnl_pct,
      win_rate, total_trades, streak, badge { id, label, emoji, color }, xp

    Used by: /leaderboard page (both HEAD and cb9d variants)

    Example: GET /leaderboard?limit=20
    """
    try:
        board = get_leaderboard(session=session, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "total_players": len(board),
        "leaderboard":   board,
    }


# ─────────────────────────────────────────────
# GET /leaderboard/me
# ─────────────────────────────────────────────

@router.get("/leaderboard/me")
def my_rank(
    telegram_user_id: Optional[str] = None,
    wallet_address: Optional[str] = None,
    session: Session = Depends(get_session),
):
    """
    Returns a single user's leaderboard entry including their rank number,
    badge, XP, streak, and an XP progress bar value.

    Used by: /leaderboard page MY RANK card (HEAD variant)

    Examples:
        GET /leaderboard/me?telegram_user_id=987654321
        GET /leaderboard/me?wallet_address=0xabc...123
    """
    tid = _resolve_tid(telegram_user_id, wallet_address)
    if not tid:
        raise HTTPException(
            status_code=400,
            detail="Provide telegram_user_id or wallet_address."
        )

    try:
        entry = get_user_rank(tid, session)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if not entry:
        raise HTTPException(status_code=404, detail="User not found on leaderboard.")

    return entry


# ─────────────────────────────────────────────
# GET /user/stats
# ─────────────────────────────────────────────

@router.get("/user/stats")
def user_stats(
    telegram_user_id: Optional[str] = None,
    wallet_address: Optional[str] = None,
    session: Session = Depends(get_session),
):
    """
    Returns XP, level, rank, streak, xpToNextLevel, xpProgress, totalTrades,
    winRate for the achievements page header ring.

    Used by: /achievements page → getUserStats() in api.js

    Examples:
        GET /user/stats?wallet_address=0xabc...123
        GET /user/stats?telegram_user_id=987654321
    """
    tid = _resolve_tid(telegram_user_id, wallet_address)
    if not tid:
        raise HTTPException(
            status_code=400,
            detail="Provide telegram_user_id or wallet_address."
        )

    try:
        stats = get_user_stats(tid, session)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return stats


# ─────────────────────────────────────────────
# GET /user/achievements
# ─────────────────────────────────────────────

@router.get("/user/achievements")
def user_achievements(
    telegram_user_id: Optional[str] = None,
    wallet_address: Optional[str] = None,
    session: Session = Depends(get_session),
):
    """
    Returns all achievement definitions annotated with earned: true/false
    for the requesting user.

    Shape of each item:
      { id, icon, name, desc, xp, earned, isNew }

    Used by: /achievements page → getAchievements() in api.js

    Examples:
        GET /user/achievements?wallet_address=0xabc...123
        GET /user/achievements?telegram_user_id=987654321
    """
    tid = _resolve_tid(telegram_user_id, wallet_address)
    if not tid:
        raise HTTPException(
            status_code=400,
            detail="Provide telegram_user_id or wallet_address."
        )

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
