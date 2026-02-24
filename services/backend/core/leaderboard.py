"""
Leaderboard logic for NORT paper trading.
Ranks all users by portfolio performance with badges and XP.
"""

from typing import List, Optional
from sqlmodel import Session, select
from services.backend.data.models import WalletConfig, PaperTrade, User


# ─────────────────────────────────────────────
# BADGE SYSTEM
# ─────────────────────────────────────────────

def compute_badge(total_trades: int, win_rate: float, net_pnl: float) -> dict:
    """Return the highest earned badge for this user."""
    if total_trades == 0:
        return {"id": "rookie", "label": "Rookie", "emoji": "🌱", "color": "#a0a0a0"}
    if net_pnl >= 500 and win_rate >= 70 and total_trades >= 20:
        return {"id": "oracle", "label": "Oracle", "emoji": "🔮", "color": "#7c3aed"}
    if net_pnl >= 250 and win_rate >= 60 and total_trades >= 10:
        return {"id": "shark", "label": "Shark", "emoji": "🦈", "color": "#0ea5e9"}
    if net_pnl >= 100 and total_trades >= 5:
        return {"id": "trader", "label": "Trader", "emoji": "⚡", "color": "#f59e0b"}
    if total_trades >= 1:
        return {"id": "degen", "label": "Degen", "emoji": "🎲", "color": "#10b981"}
    return {"id": "rookie", "label": "Rookie", "emoji": "🌱", "color": "#a0a0a0"}


def compute_xp(total_trades: int, win_rate: float, net_pnl: float) -> int:
    """XP formula: trades + win bonus + profit bonus."""
    xp = total_trades * 10
    if win_rate >= 50:
        xp += int((win_rate - 50) * 4)
    if net_pnl > 0:
        xp += int(net_pnl * 0.5)
    return max(0, xp)


def compute_streak(trades: list) -> int:
    """Count current consecutive winning closed trades."""
    closed = sorted(
        [t for t in trades if t.status == "CLOSED" and t.pnl is not None],
        key=lambda t: t.closed_at or t.created_at,
        reverse=True,
    )
    streak = 0
    for t in closed:
        if t.pnl > 0:
            streak += 1
        else:
            break
    return streak


# ─────────────────────────────────────────────
# MAIN LEADERBOARD QUERY
# ─────────────────────────────────────────────

def get_leaderboard(session: Session, limit: int = 50) -> List[dict]:
    """
    Build ranked leaderboard from all WalletConfig + PaperTrade records.
    Sorted by total_portfolio_value descending.
    """
    configs = session.exec(select(WalletConfig)).all()
    all_trades = session.exec(select(PaperTrade)).all()
    all_users = session.exec(select(User)).all()

    # Index trades and users by telegram_user_id
    trades_by_user: dict = {}
    for t in all_trades:
        trades_by_user.setdefault(t.telegram_user_id, []).append(t)

    user_by_tid: dict = {}
    for u in all_users:
        if u.telegram_id:
            user_by_tid[u.telegram_id] = u
        if u.wallet_address:
            user_by_tid[u.wallet_address.lower()] = u

    rows = []
    for config in configs:
        tid = config.telegram_user_id
        trades = trades_by_user.get(tid, [])
        user = user_by_tid.get(tid)

        open_trades   = [t for t in trades if t.status == "OPEN"]
        closed_trades = [t for t in trades if t.status == "CLOSED"]
        winning       = [t for t in closed_trades if (t.pnl or 0) > 0]

        open_cost         = sum(t.total_cost for t in open_trades)
        realized_pnl      = sum(t.pnl or 0 for t in closed_trades)
        portfolio_value   = round(config.paper_balance + open_cost, 2)
        net_pnl           = round(portfolio_value - config.total_deposited + realized_pnl, 2)
        total_trades      = len(trades)
        win_rate          = round((len(winning) / len(closed_trades)) * 100, 1) if closed_trades else 0.0
        streak            = compute_streak(trades)
        badge             = compute_badge(total_trades, win_rate, net_pnl)
        xp                = compute_xp(total_trades, win_rate, net_pnl)

        # Display name: username > wallet short > telegram id short
        if user and user.username:
            display_name = user.username
        elif user and user.wallet_address:
            wa = user.wallet_address
            display_name = f"{wa[:6]}...{wa[-4:]}"
        else:
            display_name = f"Trader {tid[:6]}"

        rows.append({
            "telegram_user_id":  tid,
            "display_name":      display_name,
            "portfolio_value":   portfolio_value,
            "net_pnl":           net_pnl,
            "net_pnl_pct":       round((net_pnl / config.total_deposited) * 100, 2),
            "paper_balance":     round(config.paper_balance, 2),
            "total_trades":      total_trades,
            "open_trades":       len(open_trades),
            "closed_trades":     len(closed_trades),
            "win_rate":          win_rate,
            "streak":            streak,
            "badge":             badge,
            "xp":                xp,
        })

    # Sort: portfolio value desc, then net_pnl desc
    rows.sort(key=lambda r: (r["portfolio_value"], r["net_pnl"]), reverse=True)

    # Add rank
    for i, row in enumerate(rows[:limit]):
        row["rank"] = i + 1

    return rows[:limit]


def get_user_rank(telegram_user_id: str, session: Session) -> Optional[dict]:
    """Get a single user's leaderboard entry with their rank."""
    board = get_leaderboard(session, limit=1000)
    for entry in board:
        if entry["telegram_user_id"] == str(telegram_user_id):
            return entry
    return None
