"""
Core paper trading logic for Polymarket AI Assistant.
Intern 5 - Paper Trading & Wallet

Handles:
- Wallet creation and management
- Placing paper trades (BUY/SELL)
- Settling trades against resolved market outcomes
- P&L calculation (win/loss)
"""

import hashlib
import time
import httpx
import os
from datetime import datetime
from typing import Optional
from sqlmodel import Session, select

from services.backend.data.models import User, WalletConfig, PaperTrade, Market


# ─────────────────────────────────────────────
# USER / WALLET HELPERS
# ─────────────────────────────────────────────

def connect_wallet(
    wallet_address: str,
    session: Session,
    telegram_id: Optional[str] = None,
    username: Optional[str] = None,
) -> User:
    wallet_address = wallet_address.lower()
    statement = select(User).where(User.wallet_address == wallet_address)
    user = session.exec(statement).first()

    if not user:
        user = User(wallet_address=wallet_address, telegram_id=telegram_id, username=username)
        session.add(user)
        session.commit()
        session.refresh(user)
    else:
        changed = False
        if telegram_id and user.telegram_id != telegram_id:
            user.telegram_id = telegram_id
            changed = True
        if username and user.username != username:
            user.username = username
            changed = True
        if changed:
            session.add(user)
            session.commit()
            session.refresh(user)

    config_key = user.telegram_id or user.wallet_address
    _ensure_wallet_config(config_key, session)
    return user


def _ensure_wallet_config(telegram_user_id: str, session: Session) -> WalletConfig:
    statement = select(WalletConfig).where(WalletConfig.telegram_user_id == str(telegram_user_id))
    config = session.exec(statement).first()
    if not config:
        config = WalletConfig(
            telegram_user_id=str(telegram_user_id),
            paper_balance=1000.0,
            total_deposited=1000.0,
        )
        session.add(config)
        session.commit()
        session.refresh(config)
    return config


def get_user_by_wallet(wallet_address: str, session: Session) -> Optional[User]:
    statement = select(User).where(User.wallet_address == wallet_address.lower())
    return session.exec(statement).first()


def get_user_by_telegram(telegram_id: str, session: Session) -> Optional[User]:
    statement = select(User).where(User.telegram_id == str(telegram_id))
    return session.exec(statement).first()


# ─────────────────────────────────────────────
# PLACE A PAPER TRADE
# ─────────────────────────────────────────────

def place_paper_trade(
    telegram_user_id: str,
    market_id: str,
    market_question: str,
    outcome: str,
    shares: float,
    price_per_share: float,
    direction: str,
    session: Session,
) -> PaperTrade:
    telegram_user_id = str(telegram_user_id)

    if outcome.upper() not in ("YES", "NO"):
        raise ValueError("Outcome must be 'YES' or 'NO'.")
    if direction.upper() not in ("BUY", "SELL"):
        raise ValueError("Direction must be 'BUY' or 'SELL'.")
    if not (0 < price_per_share < 1):
        raise ValueError("price_per_share must be between 0 and 1.")
    if shares <= 0:
        raise ValueError("Shares must be greater than 0.")

    total_cost = round(shares * price_per_share, 6)
    if total_cost < 1.0:
        raise ValueError("Minimum trade value is 1 paper USDC.")

    config = _ensure_wallet_config(telegram_user_id, session)

    if direction.upper() == "BUY" and config.paper_balance < total_cost:
        raise ValueError(
            f"Insufficient balance. Have ${config.paper_balance:.2f}, need ${total_cost:.2f}."
        )

    if direction.upper() == "BUY":
        config.paper_balance = round(config.paper_balance - total_cost, 6)
        config.updated_at = datetime.utcnow()
        session.add(config)

    trade = PaperTrade(
        telegram_user_id=telegram_user_id,
        market_id=market_id,
        market_question=market_question,
        outcome=outcome.upper(),
        shares=shares,
        price_per_share=price_per_share,
        total_cost=total_cost,
        direction=direction.upper(),
        status="OPEN",
    )
    session.add(trade)
    session.commit()
    session.refresh(trade)
    return trade


# ─────────────────────────────────────────────
# SETTLE A TRADE — this is what calculates WIN/LOSS
# ─────────────────────────────────────────────

def _get_market_resolution(market_id: str) -> Optional[str]:
    """
    Check Polymarket API to see if a market has resolved.
    Returns "YES", "NO", or None if still open.
    """
    try:
        url = f"{os.getenv('POLYMARKET_API_URL', 'https://gamma-api.polymarket.com')}/markets/{market_id}"
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url)
            if response.status_code != 200:
                return None
            data = response.json()

        # Market is resolved when active=false and there's a winner
        if data.get("active", True):
            return None  # Still running

        # outcomePrices: resolved market has one outcome at 1.0 and the rest at 0.0
        outcomes = data.get("outcomes", ["YES", "NO"])
        prices_raw = data.get("outcomePrices", "[]")
        if isinstance(prices_raw, str):
            import json
            prices_raw = json.loads(prices_raw)

        prices = [float(p) for p in prices_raw]

        for i, price in enumerate(prices):
            if price >= 0.99:  # resolved winner = price of 1.0
                return outcomes[i] if i < len(outcomes) else ("YES" if i == 0 else "NO")

        return None
    except Exception as e:
        print(f"[settle] Could not fetch resolution for {market_id}: {e}")
        return None


def settle_trade(trade_id: int, session: Session) -> dict:
    """
    Check if a trade's market has resolved and calculate P&L.

    WIN:  user bet YES and market resolved YES → payout = shares * 1.0
          user bet NO  and market resolved NO  → payout = shares * 1.0
    LOSE: user bet the wrong outcome → payout = 0, lose total_cost

    Returns a dict with result details.
    """
    trade = session.get(PaperTrade, trade_id)
    if not trade:
        raise ValueError(f"Trade {trade_id} not found.")
    if trade.status != "OPEN":
        return {
            "trade_id": trade_id,
            "status": trade.status,
            "pnl": trade.pnl,
            "message": "Trade already settled."
        }

    resolution = _get_market_resolution(trade.market_id)

    if resolution is None:
        return {
            "trade_id": trade_id,
            "status": "OPEN",
            "pnl": None,
            "message": "Market has not resolved yet."
        }

    # Calculate P&L
    won = (trade.outcome == resolution)

    if won:
        # Payout = shares × $1.00 (full dollar per share on win)
        payout = round(trade.shares * 1.0, 6)
        pnl = round(payout - trade.total_cost, 6)  # profit = payout minus what we paid
        result = "WIN"
    else:
        payout = 0.0
        pnl = round(-trade.total_cost, 6)  # loss = everything we spent
        result = "LOSS"

    # Update trade
    trade.status = "CLOSED"
    trade.pnl = pnl
    trade.closed_at = datetime.utcnow()
    session.add(trade)

    # Credit payout back to wallet balance
    config_stmt = select(WalletConfig).where(WalletConfig.telegram_user_id == trade.telegram_user_id)
    config = session.exec(config_stmt).first()
    if config and payout > 0:
        config.paper_balance = round(config.paper_balance + payout, 6)
        config.updated_at = datetime.utcnow()
        session.add(config)

    session.commit()

    return {
        "trade_id": trade_id,
        "market_id": trade.market_id,
        "market_question": trade.market_question,
        "your_bet": trade.outcome,
        "market_resolved": resolution,
        "result": result,
        "shares": trade.shares,
        "cost": trade.total_cost,
        "payout": payout,
        "pnl": pnl,
        "status": "CLOSED",
        "closed_at": trade.closed_at.isoformat(),
    }


def settle_all_open_trades(telegram_user_id: str, session: Session) -> list:
    """
    Try to settle every open trade for a user.
    Called by /wallet/settle or the Telegram /portfolio command.
    """
    stmt = select(PaperTrade).where(
        PaperTrade.telegram_user_id == str(telegram_user_id),
        PaperTrade.status == "OPEN"
    )
    open_trades = session.exec(stmt).all()

    results = []
    for trade in open_trades:
        result = settle_trade(trade.id, session)
        results.append(result)

    return results


# ─────────────────────────────────────────────
# WALLET SUMMARY
# ─────────────────────────────────────────────

def get_wallet_summary(
    session: Session,
    wallet_address: Optional[str] = None,
    telegram_user_id: Optional[str] = None,
) -> dict:
    if wallet_address and not telegram_user_id:
        wallet_address = wallet_address.lower()
        user = get_user_by_wallet(wallet_address, session)
        telegram_user_id = (user.telegram_id or user.wallet_address) if user else wallet_address
    elif telegram_user_id and not wallet_address:
        user = get_user_by_telegram(telegram_user_id, session)
        wallet_address = user.wallet_address if user else None

    if not telegram_user_id:
        raise ValueError("Could not resolve a telegram_user_id.")

    config = _ensure_wallet_config(telegram_user_id, session)

    trades_stmt = select(PaperTrade).where(PaperTrade.telegram_user_id == str(telegram_user_id))
    trades = session.exec(trades_stmt).all()

    open_trades   = [t for t in trades if t.status == "OPEN"]
    closed_trades = [t for t in trades if t.status == "CLOSED"]
    wins          = [t for t in closed_trades if (t.pnl or 0) > 0]
    losses        = [t for t in closed_trades if (t.pnl or 0) <= 0]

    total_realized_pnl  = round(sum(t.pnl or 0.0 for t in closed_trades), 2)
    open_positions_cost = round(sum(t.total_cost for t in open_trades), 2)
    total_value         = round(config.paper_balance + open_positions_cost, 2)
    net_pnl             = round(total_value - config.total_deposited + total_realized_pnl, 2)
    win_rate            = round((len(wins) / len(closed_trades)) * 100, 1) if closed_trades else 0.0

    return {
        "wallet_address":       wallet_address,
        "telegram_user_id":     telegram_user_id,
        "paper_balance":        round(config.paper_balance, 2),
        "open_positions_cost":  open_positions_cost,
        "total_portfolio_value": total_value,
        "total_realized_pnl":   total_realized_pnl,
        "net_pnl":              net_pnl,
        "total_trades":         len(trades),
        "open_trades_count":    len(open_trades),
        "closed_trades_count":  len(closed_trades),
        "wins":                 len(wins),
        "losses":               len(losses),
        "win_rate_pct":         win_rate,
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
                "result":          ("WIN" if (t.pnl or 0) > 0 else "LOSS") if t.status == "CLOSED" else "OPEN",
                "pnl":             t.pnl,
                "closed_at":       t.closed_at.isoformat() if t.closed_at else None,
                "created_at":      t.created_at.isoformat(),
            }
            for t in trades
        ],
    }


# ─────────────────────────────────────────────
# OPTIONAL: TESTNET COMMIT
# ─────────────────────────────────────────────

def commit_trade_to_testnet(trade_id: int, session: Session) -> str:
    trade = session.get(PaperTrade, trade_id)
    if not trade:
        raise ValueError(f"Trade ID {trade_id} not found.")
    if trade.tx_hash:
        return trade.tx_hash

    raw = f"TESTNET-{trade.id}-{trade.telegram_user_id}-{trade.created_at}-{time.time()}"
    mock_hash = "0x" + hashlib.sha256(raw.encode()).hexdigest()
    trade.tx_hash = mock_hash
    session.add(trade)
    session.commit()
    return mock_hash
