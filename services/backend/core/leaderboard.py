"""
Leaderboard + Achievements + User Stats core logic for NORT.

Feeds:
  GET /leaderboard           → full ranked board
  GET /leaderboard/me        → personal rank card
  GET /user/stats            → XP, level, streak, rank (achievements page header)
  GET /user/achievements     → earned / locked achievement list
"""

from typing import List, Optional
from sqlmodel import Session, select
from services.backend.data.models import WalletConfig, PaperTrade, User


# ─────────────────────────────────────────────
# ACHIEVEMENT DEFINITIONS
# Single source of truth — both backend and the
# frontend achievements page read from this.
# ─────────────────────────────────────────────

ACHIEVEMENT_DEFS = [
    {"id": "first",   "icon": "🎯", "name": "First Trade",    "desc": "Complete your first paper trade",        "xp": 50},
    {"id": "bullish", "icon": "📈", "name": "Bullish",        "desc": "Finish a trade in profit",               "xp": 100},
    {"id": "vip",     "icon": "⭐", "name": "VIP",            "desc": "Unlock premium advice",                  "xp": 200},
    {"id": "moon",    "icon": "🌙", "name": "Moon Hunter",    "desc": "Catch a hot signal and profit from it",  "xp": 150},
    {"id": "contra",  "icon": "🦄", "name": "Contrarian",     "desc": "Win a trade where YES odds were < 30%",  "xp": 250},
    {"id": "paper",   "icon": "📝", "name": "Paper Hands",    "desc": "Complete 10 trades",                     "xp": 100},
    {"id": "onfire",  "icon": "🔥", "name": "On Fire",        "desc": "5-trade winning streak",                 "xp": 300},
    {"id": "diamond", "icon": "💎", "name": "Diamond Hands",  "desc": "Hold a position until market closes",    "xp": 200},
    {"id": "degen",   "icon": "🎰", "name": "Degenerate",     "desc": "10-trade winning streak",                "xp": 500},
    {"id": "whale",   "icon": "🐳", "name": "Whale",          "desc": "Complete 50 trades",                     "xp": 750},
]


# ─────────────────────────────────────────────
# BADGE SYSTEM
# ─────────────────────────────────────────────

def compute_badge(total_trades: int, win_rate: float, net_pnl: float) -> dict:
    """Return the highest earned badge for this user."""
    if net_pnl >= 500 and win_rate >= 70 and total_trades >= 20:
        return {"id": "oracle",  "label": "Oracle", "emoji": "🔮", "color": "#7c3aed"}
    if net_pnl >= 250 and win_rate >= 60 and total_trades >= 10:
        return {"id": "shark",   "label": "Shark",  "emoji": "🦈", "color": "#0ea5e9"}
    if net_pnl >= 100 and total_trades >= 5:
        return {"id": "trader",  "label": "Trader", "emoji": "⚡", "color": "#f59e0b"}
    if total_trades >= 1:
        return {"id": "degen",   "label": "Degen",  "emoji": "🎲", "color": "#10b981"}
    return     {"id": "rookie",  "label": "Rookie", "emoji": "🌱", "color": "#a0a0a0"}


# ─────────────────────────────────────────────
# XP FORMULA
# ─────────────────────────────────────────────

def compute_xp(total_trades: int, win_rate: float, net_pnl: float) -> int:
    """XP = 10 per trade + win-rate bonus + profit bonus."""
    xp = total_trades * 10
    if win_rate >= 50:
        xp += int((win_rate - 50) * 4)
    if net_pnl > 0:
        xp += int(net_pnl * 0.5)
    return max(0, xp)


# ─────────────────────────────────────────────
# STREAK
# ─────────────────────────────────────────────

def compute_streak(trades: list) -> int:
    """Count current consecutive winning closed trades (most recent first)."""
    closed = sorted(
        [t for t in trades if t.status == "CLOSED" and t.pnl is not None],
        key=lambda t: t.closed_at or t.created_at,
        reverse=True,
    )
    streak = 0
    for t in closed:
        if (t.pnl or 0) > 0:
            streak += 1
        else:
            break
    return streak


# ─────────────────────────────────────────────
# ACHIEVEMENTS CHECK
# ─────────────────────────────────────────────

def check_achievements(
    trades: list,
    net_pnl: float,
    has_used_premium: bool = False,
) -> List[dict]:
    """
    Given a user's trade list, return all achievement defs annotated
    with earned: True/False and isNew: False.
    Frontend drives the 'isNew' animation — backend just reports earned state.
    """
    total_trades   = len(trades)
    closed_trades  = [t for t in trades if t.status == "CLOSED"]
    winning_trades = [t for t in closed_trades if (t.pnl or 0) > 0]
    streak         = compute_streak(trades)

    # Contrarian: won a trade where odds at time were low (price_per_share < 0.30)
    contrarian_wins = [
        t for t in winning_trades
        if (t.price_per_share or 1) < 0.30
    ]

    earned_map = {
        "first":   total_trades >= 1,
        "bullish": len(winning_trades) >= 1,
        "vip":     has_used_premium,
        "moon":    total_trades >= 1 and net_pnl > 0,
        "contra":  len(contrarian_wins) >= 1,
        "paper":   total_trades >= 10,
        "onfire":  streak >= 5,
        "diamond": len(closed_trades) >= 5,
        "degen":   streak >= 10,
        "whale":   total_trades >= 50,
    }

    return [
        {**defn, "earned": earned_map.get(defn["id"], False), "isNew": False}
        for defn in ACHIEVEMENT_DEFS
    ]


# ─────────────────────────────────────────────
# SHARED — load a user's raw data
# ─────────────────────────────────────────────

def _load_user_data(tid: str, session: Session):
    """Return (config, trades, user) for a telegram_user_id."""
    config = session.exec(
        select(WalletConfig).where(WalletConfig.telegram_user_id == tid)
    ).first()

    trades = session.exec(
        select(PaperTrade).where(PaperTrade.telegram_user_id == tid)
    ).all()

    # Try to find user by telegram_id or wallet_address
    user = session.exec(
        select(User).where(User.telegram_id == tid)
    ).first()
    if not user:
        user = session.exec(
            select(User).where(User.wallet_address == tid.lower())
        ).first()

    return config, list(trades), user


def _display_name(user: Optional[User], tid: str) -> str:
    if user and user.username:
        return user.username
    if user and user.wallet_address:
        wa = user.wallet_address
        return f"{wa[:6]}...{wa[-4:]}"
    return f"Trader {tid[:6]}"


# ─────────────────────────────────────────────
# LEADERBOARD
# ─────────────────────────────────────────────

def get_leaderboard(session: Session, limit: int = 50) -> List[dict]:
    """
    Build ranked leaderboard from all WalletConfig + PaperTrade records.
    Sorted by portfolio_value desc, then net_pnl desc.
    """
    configs    = session.exec(select(WalletConfig)).all()
    all_trades = session.exec(select(PaperTrade)).all()
    all_users  = session.exec(select(User)).all()

    trades_by_user: dict = {}
    for t in all_trades:
        trades_by_user.setdefault(t.telegram_user_id, []).append(t)

    user_by_tid: dict = {}
    for u in all_users:
        if u.telegram_id:
            user_by_tid[u.telegram_id] = u
        if u.wallet_address:
            # Index by both original and lowercase — WalletConfig.telegram_user_id is lowercase
            user_by_tid[u.wallet_address] = u
            user_by_tid[u.wallet_address.lower()] = u

    rows = []
    for config in configs:
        tid    = config.telegram_user_id
        trades = trades_by_user.get(tid, [])
        user   = user_by_tid.get(tid)

        open_trades   = [t for t in trades if t.status == "OPEN"]
        closed_trades = [t for t in trades if t.status == "CLOSED"]
        winning       = [t for t in closed_trades if (t.pnl or 0) > 0]

        open_cost       = sum(t.total_cost for t in open_trades)
        portfolio_value = round(config.paper_balance + open_cost, 2)
        # net_pnl = how much above/below the starting $1000 the user is.
        # paper_balance already reflects all closed trade payouts, so we
        # do NOT add realized_pnl again — that would double-count it.
        net_pnl         = round(portfolio_value - config.total_deposited, 2)
        total_trades    = len(trades)
        win_rate        = round(len(winning) / len(closed_trades) * 100, 1) if closed_trades else 0.0
        streak          = compute_streak(trades)
        badge           = compute_badge(total_trades, win_rate, net_pnl)
        xp              = compute_xp(total_trades, win_rate, net_pnl)

        rows.append({
            "telegram_user_id": tid,
            "display_name":     _display_name(user, tid),
            "portfolio_value":  portfolio_value,
            "net_pnl":          net_pnl,
            "net_pnl_pct":      round((net_pnl / config.total_deposited) * 100, 2) if config.total_deposited else 0,
            "paper_balance":    round(config.paper_balance, 2),
            "total_trades":     total_trades,
            "open_trades":      len(open_trades),
            "closed_trades":    len(closed_trades),
            "win_rate":         win_rate,
            "streak":           streak,
            "badge":            badge,
            "xp":               xp,
        })

    rows.sort(key=lambda r: (r["portfolio_value"], r["net_pnl"]), reverse=True)
    for i, row in enumerate(rows[:limit]):
        row["rank"] = i + 1

    return rows[:limit]


def get_user_rank(telegram_user_id: str, session: Session) -> Optional[dict]:
    """Get a single user's full leaderboard entry including their rank."""
    board = get_leaderboard(session, limit=10_000)
    for entry in board:
        if entry["telegram_user_id"] == str(telegram_user_id):
            return entry
    return None


# ─────────────────────────────────────────────
# USER STATS (achievements page header)
# ─────────────────────────────────────────────

def get_user_stats(tid: str, session: Session) -> dict:
    """
    Return XP, level, rank, streak, xpToNextLevel, xpProgress for
    the achievements page ring + header.
    """
    config, trades, user = _load_user_data(tid, session)
    if not config:
        return {
            "xp": 0, "level": 1, "rank": None, "streak": 0,
            "xpToNextLevel": 500, "xpProgress": 0,
            "totalTrades": 0, "winRate": 0,
        }

    closed_trades  = [t for t in trades if t.status == "CLOSED"]
    winning_trades = [t for t in closed_trades if (t.pnl or 0) > 0]
    open_cost      = sum(t.total_cost for t in trades if t.status == "OPEN")
    portfolio_value = round(config.paper_balance + open_cost, 2)
    net_pnl         = round(portfolio_value - config.total_deposited, 2)

    win_rate   = round(len(winning_trades) / len(closed_trades) * 100, 1) if closed_trades else 0.0
    streak     = compute_streak(trades)
    xp         = compute_xp(len(trades), win_rate, net_pnl)
    level      = (xp // 500) + 1
    xp_in_lvl  = xp % 500
    xp_needed  = 500 - xp_in_lvl

    # Rank: need the full board
    board = get_leaderboard(session, limit=10_000)
    rank  = next((e["rank"] for e in board if e["telegram_user_id"] == tid), None)

    return {
        "xp":            xp,
        "level":         level,
        "rank":          rank,
        "streak":        streak,
        "xpToNextLevel": xp_needed,
        "xpProgress":    round((xp_in_lvl / 500) * 100, 1),
        "totalTrades":   len(trades),
        "winRate":       win_rate,
    }


# ─────────────────────────────────────────────
# ACHIEVEMENTS (per-user)
# ─────────────────────────────────────────────

def get_achievements(tid: str, session: Session) -> List[dict]:
    """Return all achievements annotated with earned state for this user."""
    config, trades, _ = _load_user_data(tid, session)
    if not config:
        return [dict(a, earned=False, isNew=False) for a in ACHIEVEMENT_DEFS]

    closed_trades = [t for t in trades if t.status == "CLOSED"]
    open_cost     = sum(t.total_cost for t in trades if t.status == "OPEN")
    portfolio_value = round(config.paper_balance + open_cost, 2)
    net_pnl         = round(portfolio_value - config.total_deposited, 2)

    return check_achievements(trades=trades, net_pnl=net_pnl)
