"""
Leaderboard + Achievements + User Stats core logic for NORT.

Supports two modes:
  mode='paper'  → reads PaperTrade + paper_balance (original behaviour)
  mode='real'   → reads RealTrade  + real_balance_usdc

The mode is read directly from WalletConfig.trading_mode so every
endpoint automatically shows the right data for the user's current mode.
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

INITIAL_DEPOSIT = 1000.0  # Starting balance for both paper and real mode


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
    """Count consecutive winning trades from most recent backwards."""
    # Support both PaperTrade (status='CLOSED') and RealTrade (status='closed')
    closed = sorted(
        [t for t in trades if str(getattr(t, 'status', '')).upper() == "CLOSED" and t.pnl is not None],
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


# ─── TRADE LOADER (mode-aware) ────────────────────────────────────────────────

def _load_trades_for_user(tid: str, mode: str, session: Session) -> list:
    """
    Load the right trade table based on mode.
    paper → PaperTrade
    real  → RealTrade
    """
    if mode == "real":
        return list(session.exec(
            select(RealTrade).where(RealTrade.telegram_user_id == tid)
        ).all())
    else:
        return list(session.exec(
            select(PaperTrade).where(PaperTrade.telegram_user_id == tid)
        ).all())


def _load_user_data(tid: str, session: Session, mode: str = None):
    """
    Load config, trades (correct table for mode), and user record.
    If mode is None, reads mode from WalletConfig.
    """
    config = session.exec(
        select(WalletConfig).where(WalletConfig.telegram_user_id == tid)
    ).first()

    effective_mode = mode or (getattr(config, 'trading_mode', 'paper') if config else 'paper')
    trades = _load_trades_for_user(tid, effective_mode, session)

    user = session.exec(select(User).where(User.telegram_id == tid)).first()
    if not user:
        user = session.exec(select(User).where(User.wallet_address == tid.lower())).first()

    return config, trades, user, effective_mode


# ─── STAT HELPERS ────────────────────────────────────────────────────────────

def _compute_stats_from_trades(trades: list, balance: float, deposited: float) -> dict:
    """
    Compute all stats that change based on trade history.
    Works for both PaperTrade and RealTrade lists.
    """
    # Normalise status — PaperTrade uses 'OPEN'/'CLOSED', RealTrade uses lowercase
    closed_trades = [t for t in trades if str(getattr(t, 'status', '')).upper() == 'CLOSED']
    open_trades   = [t for t in trades if str(getattr(t, 'status', '')).upper() not in ('CLOSED',)]
    winning       = [t for t in closed_trades if (t.pnl or 0) > 0]
    losing        = [t for t in closed_trades if (t.pnl or 0) < 0]

    # Cost field differs between models
    def _cost(t):
        return getattr(t, 'total_cost', None) or getattr(t, 'total_cost_usdc', 0) or 0

    open_cost       = sum(_cost(t) for t in open_trades)
    portfolio_value = round(balance + open_cost, 2)
    net_pnl         = round(portfolio_value - deposited, 2)
    net_pnl_pct     = round((net_pnl / deposited) * 100, 2) if deposited else 0
    win_rate        = round(len(winning) / len(closed_trades) * 100, 1) if closed_trades else 0.0
    streak          = compute_streak(trades)

    return {
        "portfolio_value": portfolio_value,
        "net_pnl":         net_pnl,
        "net_pnl_pct":     net_pnl_pct,
        "total_trades":    len(trades),
        "open_trades":     len(open_trades),
        "closed_trades":   len(closed_trades),
        "wins":            len(winning),
        "losses":          len(losing),
        "win_rate":        win_rate,
        "streak":          streak,
    }


# ─── ACHIEVEMENTS ────────────────────────────────────────────────────────────

def check_achievements(trades: list, net_pnl: float, has_used_premium: bool = False) -> List[dict]:
    total_trades   = len(trades)
    closed_trades  = [t for t in trades if str(getattr(t, 'status', '')).upper() == "CLOSED"]
    winning_trades = [t for t in closed_trades if (t.pnl or 0) > 0]
    streak         = compute_streak(trades)

    def _price(t):
        return getattr(t, 'price_per_share', None) or getattr(t, 'price_per_share', 1) or 1

    contrarian_wins = [t for t in winning_trades if _price(t) < 0.30]

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
        if u.telegram_id:    idx[u.telegram_id] = u
        if u.wallet_address: idx[u.wallet_address] = u
        if u.wallet_address: idx[u.wallet_address.lower()] = u
    return idx


# ─── PAPER LEADERBOARD ───────────────────────────────────────────────────────

def _paper_leaderboard(session: Session, limit: int) -> List[dict]:
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

        user  = user_idx.get(tid)
        stats = _compute_stats_from_trades(trades, config.paper_balance, config.total_deposited)

        rows.append({
            "telegram_user_id": tid,
            "display_name":     _display_name(user, tid),
            **stats,
            "paper_balance":    round(config.paper_balance, 2),
            "badge":            compute_badge(stats["total_trades"], stats["win_rate"], stats["net_pnl"]),
            "xp":               compute_xp(stats["total_trades"], stats["win_rate"], stats["net_pnl"]),
            "mode":             "paper",
        })

    rows.sort(key=lambda r: (r["portfolio_value"], r["net_pnl"]), reverse=True)
    for i, row in enumerate(rows[:limit]):
        row["rank"] = i + 1
    return rows[:limit]


# ─── REAL LEADERBOARD ────────────────────────────────────────────────────────

def _real_leaderboard(session: Session, limit: int) -> List[dict]:
    configs    = session.exec(select(WalletConfig)).all()
    all_trades = session.exec(select(RealTrade)).all()
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

        user  = user_idx.get(tid)
        stats = _compute_stats_from_trades(trades, config.real_balance_usdc, INITIAL_DEPOSIT)

        rows.append({
            "telegram_user_id":  tid,
            "display_name":      _display_name(user, tid),
            **stats,
            "real_balance_usdc": round(config.real_balance_usdc, 2),
            "badge":             compute_badge(stats["total_trades"], stats["win_rate"], stats["net_pnl"]),
            "xp":                compute_xp(stats["total_trades"], stats["win_rate"], stats["net_pnl"]),
            "mode":              "real",
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
    """
    Returns stats for the user's CURRENT trading mode.
    Automatically reads WalletConfig.trading_mode to choose paper or real.
    """
    config, trades, user, mode = _load_user_data(tid, session)
    if not config:
        return {
            "xp": 0, "level": 1, "rank": None, "streak": 0,
            "xpToNextLevel": 500, "xpProgress": 0,
            "totalTrades": 0, "winRate": 0,
            "mode": "paper",
        }

    balance   = config.real_balance_usdc if mode == "real" else config.paper_balance
    deposited = INITIAL_DEPOSIT

    stats    = _compute_stats_from_trades(trades, balance, deposited)
    xp       = compute_xp(stats["total_trades"], stats["win_rate"], stats["net_pnl"])
    level    = (xp // 500) + 1
    xp_in_lvl = xp % 500
    board    = get_leaderboard(session, limit=10_000, mode=mode)
    rank     = next((e["rank"] for e in board if e["telegram_user_id"] == tid), None)

    return {
        "xp":            xp,
        "level":         level,
        "rank":          rank,
        "streak":        stats["streak"],
        "xpToNextLevel": 500 - xp_in_lvl,
        "xpProgress":    round((xp_in_lvl / 500) * 100, 1),
        "totalTrades":   stats["total_trades"],
        "winRate":       stats["win_rate"],
        "wins":          stats["wins"],
        "losses":        stats["losses"],
        "netPnl":        stats["net_pnl"],
        "winRate":       stats["win_rate"],
        "mode":          mode,
    }


def get_achievements(tid: str, session: Session) -> List[dict]:
    """Achievements are based on current mode's trade history."""
    config, trades, _, mode = _load_user_data(tid, session)
    if not config:
        return [dict(a, earned=False, isNew=False) for a in ACHIEVEMENT_DEFS]

    balance   = config.real_balance_usdc if mode == "real" else config.paper_balance
    open_cost = sum(
        (getattr(t, 'total_cost', None) or getattr(t, 'total_cost_usdc', 0) or 0)
        for t in trades if str(getattr(t, 'status', '')).upper() not in ('CLOSED',)
    )
    net_pnl = round(balance + open_cost - INITIAL_DEPOSIT, 2)
    return check_achievements(trades=trades, net_pnl=net_pnl)
