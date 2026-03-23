"""
Leaderboard + Achievements + User Stats core logic for NORT.

Supports two modes:
  mode='paper'  → reads PaperTrade + paper_balance (original behaviour)
  mode='real'   → reads RealTrade  + real_balance_usdc

Feeds:
  GET /leaderboard?mode=paper|real
  GET /leaderboard/me?mode=paper|real
  GET /user/stats
  GET /user/achievements
"""

from typing import List, Optional
from sqlmodel import Session, select
from services.backend.data.models import WalletConfig, PaperTrade, RealTrade, User


# ─── ACHIEVEMENT DEFINITIONS ─────────────────────────────────────────────────

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


# ─── BADGE + XP + STREAK ─────────────────────────────────────────────────────

def compute_badge(total_trades: int, win_rate: float, net_pnl: float) -> dict:
    if net_pnl >= 500 and win_rate >= 70 and total_trades >= 20:
        return {"id": "oracle",  "label": "Oracle", "emoji": "🔮", "color": "#7c3aed"}
    if net_pnl >= 250 and win_rate >= 60 and total_trades >= 10:
        return {"id": "shark",   "label": "Shark",  "emoji": "🦈", "color": "#0ea5e9"}
    if net_pnl >= 100 and total_trades >= 5:
        return {"id": "trader",  "label": "Trader", "emoji": "⚡", "color": "#f59e0b"}
    if total_trades >= 1:
        return {"id": "degen",   "label": "Degen",  "emoji": "🎲", "color": "#10b981"}
    return     {"id": "rookie",  "label": "Rookie", "emoji": "🌱", "color": "#a0a0a0"}


def compute_xp(total_trades: int, win_rate: float, net_pnl: float) -> int:
    xp = total_trades * 10
    if win_rate >= 50:
        xp += int((win_rate - 50) * 4)
    if net_pnl > 0:
        xp += int(net_pnl * 0.5)
    return max(0, xp)


def compute_streak(trades: list) -> int:
    closed = sorted(
        [t for t in trades if getattr(t, 'status', '') == "CLOSED" and t.pnl is not None],
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


# ─── ACHIEVEMENTS ────────────────────────────────────────────────────────────

def check_achievements(trades: list, net_pnl: float, has_used_premium: bool = False) -> List[dict]:
    total_trades   = len(trades)
    closed_trades  = [t for t in trades if getattr(t, 'status', '') == "CLOSED"]
    winning_trades = [t for t in closed_trades if (t.pnl or 0) > 0]
    streak         = compute_streak(trades)
    contrarian_wins = [
        t for t in winning_trades
        if (getattr(t, 'price_per_share', 1) or 1) < 0.30
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


# ─── HELPERS ─────────────────────────────────────────────────────────────────

def _load_user_data(tid: str, session: Session):
    config = session.exec(
        select(WalletConfig).where(WalletConfig.telegram_user_id == tid)
    ).first()
    trades = session.exec(
        select(PaperTrade).where(PaperTrade.telegram_user_id == tid)
    ).all()
    user = session.exec(select(User).where(User.telegram_id == tid)).first()
    if not user:
        user = session.exec(select(User).where(User.wallet_address == tid.lower())).first()
    return config, list(trades), user


def _display_name(user: Optional[User], tid: str) -> str:
    if user and user.username:
        return user.username
    if user and user.wallet_address:
        wa = user.wallet_address
        return f"{wa[:6]}...{wa[-4:]}"
    return f"Trader {tid[:6]}"


def _build_user_index(session: Session) -> dict:
    all_users = session.exec(select(User)).all()
    idx = {}
    for u in all_users:
        if u.telegram_id:       idx[u.telegram_id] = u
        if u.wallet_address:    idx[u.wallet_address] = u
        if u.wallet_address:    idx[u.wallet_address.lower()] = u
    return idx


# ─── PAPER LEADERBOARD ───────────────────────────────────────────────────────

def _paper_leaderboard(session: Session, limit: int) -> List[dict]:
    """Leaderboard ranked by paper portfolio value. Original behaviour."""
    configs    = session.exec(select(WalletConfig)).all()
    all_trades = session.exec(select(PaperTrade)).all()
    user_idx   = _build_user_index(session)

    trades_by_user: dict = {}
    for t in all_trades:
        trades_by_user.setdefault(t.telegram_user_id, []).append(t)

    rows = []
    for config in configs:
        tid    = config.telegram_user_id
        trades = trades_by_user.get(tid, [])
        if not trades:
            continue

        user          = user_idx.get(tid)
        open_trades   = [t for t in trades if t.status == "OPEN"]
        closed_trades = [t for t in trades if t.status == "CLOSED"]
        winning       = [t for t in closed_trades if (t.pnl or 0) > 0]

        open_cost       = sum(t.total_cost for t in open_trades)
        portfolio_value = round(config.paper_balance + open_cost, 2)
        net_pnl         = round(portfolio_value - config.total_deposited, 2)
        total_trades    = len(trades)
        win_rate        = round(len(winning) / len(closed_trades) * 100, 1) if closed_trades else 0.0
        streak          = compute_streak(trades)

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
            "badge":            compute_badge(total_trades, win_rate, net_pnl),
            "xp":               compute_xp(total_trades, win_rate, net_pnl),
            "mode":             "paper",
        })

    rows.sort(key=lambda r: (r["portfolio_value"], r["net_pnl"]), reverse=True)
    for i, row in enumerate(rows[:limit]):
        row["rank"] = i + 1
    return rows[:limit]


# ─── REAL LEADERBOARD ────────────────────────────────────────────────────────

def _real_leaderboard(session: Session, limit: int) -> List[dict]:
    """
    Leaderboard for real trading mode.
    Ranked by real_balance_usdc + closed RealTrade P&L.
    Only users who have placed at least 1 real trade appear.
    """
    configs    = session.exec(select(WalletConfig)).all()
    all_trades = session.exec(select(RealTrade)).all()
    user_idx   = _build_user_index(session)

    trades_by_user: dict = {}
    for t in all_trades:
        trades_by_user.setdefault(t.telegram_user_id, []).append(t)

    # Initial deposit assumed to be 1000 USDC (same as paper)
    INITIAL_DEPOSIT = 1000.0

    rows = []
    for config in configs:
        tid    = config.telegram_user_id
        trades = trades_by_user.get(tid, [])
        if not trades:
            continue

        user          = user_idx.get(tid)
        closed_trades = [t for t in trades if t.status == "closed"]
        open_trades   = [t for t in trades if t.status in ("open", "pending_bridge", "bridging", "pending_execution")]
        winning       = [t for t in closed_trades if (t.pnl or 0) > 0]

        # Portfolio = current on-chain balance + open position costs
        open_cost       = sum(t.total_cost_usdc for t in open_trades)
        portfolio_value = round(config.real_balance_usdc + open_cost, 2)
        net_pnl         = round(portfolio_value - INITIAL_DEPOSIT, 2)
        total_trades    = len(trades)
        win_rate        = round(len(winning) / len(closed_trades) * 100, 1) if closed_trades else 0.0
        streak          = compute_streak(closed_trades)

        rows.append({
            "telegram_user_id": tid,
            "display_name":     _display_name(user, tid),
            "portfolio_value":  portfolio_value,
            "net_pnl":          net_pnl,
            "net_pnl_pct":      round((net_pnl / INITIAL_DEPOSIT) * 100, 2),
            "real_balance_usdc": round(config.real_balance_usdc, 2),
            "total_trades":     total_trades,
            "open_trades":      len(open_trades),
            "closed_trades":    len(closed_trades),
            "win_rate":         win_rate,
            "streak":           streak,
            "badge":            compute_badge(total_trades, win_rate, net_pnl),
            "xp":               compute_xp(total_trades, win_rate, net_pnl),
            "mode":             "real",
        })

    rows.sort(key=lambda r: (r["portfolio_value"], r["net_pnl"]), reverse=True)
    for i, row in enumerate(rows[:limit]):
        row["rank"] = i + 1
    return rows[:limit]


# ─── PUBLIC API ──────────────────────────────────────────────────────────────

def get_leaderboard(session: Session, limit: int = 50, mode: str = "paper") -> List[dict]:
    if mode == "real":
        return _real_leaderboard(session, limit)
    return _paper_leaderboard(session, limit)


def get_user_rank(telegram_user_id: str, session: Session, mode: str = "paper") -> Optional[dict]:
    board = get_leaderboard(session, limit=10_000, mode=mode)
    for entry in board:
        if entry["telegram_user_id"] == str(telegram_user_id):
            return entry
    return None


def get_user_stats(tid: str, session: Session) -> dict:
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
    board = get_leaderboard(session, limit=10_000, mode="paper")
    rank  = next((e["rank"] for e in board if e["telegram_user_id"] == tid), None)
    return {
        "xp":            xp,
        "level":         level,
        "rank":          rank,
        "streak":        streak,
        "xpToNextLevel": 500 - xp_in_lvl,
        "xpProgress":    round((xp_in_lvl / 500) * 100, 1),
        "totalTrades":   len(trades),
        "winRate":       win_rate,
    }


def get_achievements(tid: str, session: Session) -> List[dict]:
    config, trades, _ = _load_user_data(tid, session)
    if not config:
        return [dict(a, earned=False, isNew=False) for a in ACHIEVEMENT_DEFS]
    open_cost       = sum(t.total_cost for t in trades if t.status == "OPEN")
    portfolio_value = round(config.paper_balance + open_cost, 2)
    net_pnl         = round(portfolio_value - config.total_deposited, 2)
    return check_achievements(trades=trades, net_pnl=net_pnl)
