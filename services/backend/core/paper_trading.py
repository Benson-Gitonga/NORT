"""
Core paper trading logic for NORT.

Trading Mode Router
───────────────────
execute_trade() is the single entry point for all trade execution.
It checks trading_mode in WalletConfig:
  'paper' → place_paper_trade()  (no blockchain, always safe)
  'real'  → Phase 4 stub         (raises until implemented)

Mode is stored in DB only. No KYC gate. No balance gate.
Switching modes only requires user confirmation (warning modal in the UI).
"""

import hashlib
import time
import httpx
import json
import os
from datetime import datetime
from typing import Optional
from sqlmodel import Session, select

from services.backend.data.models import User, WalletConfig, PaperTrade, Market


# ─── TRADING MODE ROUTER ─────────────────────────────────────────────────────

class TradingModeError(Exception):
    pass


def execute_trade(
    telegram_user_id: str,
    market_id: str,
    market_question: str,
    outcome: str,
    shares: float,
    price_per_share: float,
    direction: str,
    session: Session,
):
    """
    Single entry point for ALL trade execution.
    Routes to paper or real engine based on DB trading_mode.
    """
    telegram_user_id = str(telegram_user_id)
    config = _ensure_wallet_config(telegram_user_id, session)

    if config.trading_mode == "paper":
        return place_paper_trade(
            telegram_user_id=telegram_user_id,
            market_id=market_id,
            market_question=market_question,
            outcome=outcome,
            shares=shares,
            price_per_share=price_per_share,
            direction=direction,
            session=session,
        )

    elif config.trading_mode == "real":
        # Phase 4: real on-chain execution — not yet implemented
        raise TradingModeError(
            "Real on-chain trading is coming in Phase 4. "
            "Switch back to paper mode to continue trading."
        )

    else:
        raise TradingModeError(f"Unknown trading mode: '{config.trading_mode}'.")


# ─── USER / WALLET HELPERS ───────────────────────────────────────────────────

def connect_wallet(wallet_address, session, telegram_id=None, username=None):
    wallet_address = wallet_address.lower()
    user = session.exec(select(User).where(User.wallet_address == wallet_address)).first()

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


def _ensure_wallet_config(telegram_user_id, session):
    config = session.exec(
        select(WalletConfig).where(WalletConfig.telegram_user_id == str(telegram_user_id))
    ).first()
    if not config:
        config = WalletConfig(
            telegram_user_id=str(telegram_user_id),
            paper_balance=1000.0,
            total_deposited=1000.0,
            trading_mode="paper",
            real_balance_usdc=0.0,
        )
        session.add(config)
        session.commit()
        session.refresh(config)
    return config


def get_user_by_wallet(wallet_address, session):
    return session.exec(select(User).where(User.wallet_address == wallet_address.lower())).first()


def get_user_by_telegram(telegram_id, session):
    return session.exec(select(User).where(User.telegram_id == str(telegram_id))).first()


# ─── PLACE A PAPER TRADE ─────────────────────────────────────────────────────

def place_paper_trade(telegram_user_id, market_id, market_question, outcome,
                      shares, price_per_share, direction, session):
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


# ─── SELL A POSITION ─────────────────────────────────────────────────────────

def sell_trade(trade_id, session):
    trade = session.get(PaperTrade, trade_id)
    if not trade:
        raise ValueError(f"Trade {trade_id} not found.")
    if trade.status != "OPEN":
        raise ValueError(f"Trade {trade_id} is already {trade.status}.")

    market = session.get(Market, str(trade.market_id))
    if market:
        current_price = float(market.current_odds) if trade.outcome == "YES" \
                        else round(1.0 - float(market.current_odds), 6)
    else:
        current_price = trade.price_per_share

    current_price = min(0.99, max(0.01, current_price))
    payout = round(trade.shares * current_price, 6)
    pnl    = round(payout - trade.total_cost, 6)

    trade.status    = "CLOSED"
    trade.pnl       = pnl
    trade.closed_at = datetime.utcnow()
    session.add(trade)

    config = session.exec(
        select(WalletConfig).where(WalletConfig.telegram_user_id == trade.telegram_user_id)
    ).first()
    if config:
        config.paper_balance = round(config.paper_balance + payout, 6)
        config.updated_at    = datetime.utcnow()
        session.add(config)

    session.commit()

    return {
        "trade_id":        trade_id,
        "market_id":       trade.market_id,
        "market_question": trade.market_question,
        "outcome":         trade.outcome,
        "shares":          trade.shares,
        "entry_price":     trade.price_per_share,
        "sell_price":      current_price,
        "cost":            trade.total_cost,
        "payout":          payout,
        "pnl":             pnl,
        "result":          "SOLD",
        "status":          "CLOSED",
        "closed_at":       trade.closed_at.isoformat(),
    }


def get_position_value(trade_id, session):
    trade = session.get(PaperTrade, trade_id)
    if not trade:
        raise ValueError(f"Trade {trade_id} not found.")

    market = session.get(Market, str(trade.market_id))
    if market:
        current_price = float(market.current_odds) if trade.outcome == "YES" \
                        else round(1.0 - float(market.current_odds), 6)
    else:
        current_price = trade.price_per_share

    current_price  = min(0.99, max(0.01, current_price))
    current_value  = round(trade.shares * current_price, 2)
    unrealized_pnl = round(current_value - trade.total_cost, 2)
    pnl_pct        = round((unrealized_pnl / trade.total_cost) * 100, 1) if trade.total_cost else 0

    return {
        "trade_id":        trade_id,
        "market_id":       trade.market_id,
        "market_question": trade.market_question,
        "outcome":         trade.outcome,
        "shares":          trade.shares,
        "entry_price":     trade.price_per_share,
        "current_price":   current_price,
        "entry_value":     trade.total_cost,
        "current_value":   current_value,
        "unrealized_pnl":  unrealized_pnl,
        "pnl_pct":         pnl_pct,
        "status":          trade.status,
    }


# ─── MARKET RESOLUTION ───────────────────────────────────────────────────────

def _get_market_resolution(market_id):
    try:
        url = f"{os.getenv('POLYMARKET_API_URL', 'https://gamma-api.polymarket.com')}/markets/{market_id}"
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url)
        if resp.status_code != 200:
            return None
        data = resp.json()
        if data.get("active", True):
            return None
        outcomes   = data.get("outcomes", ["YES", "NO"])
        prices_raw = data.get("outcomePrices", "[]")
        if isinstance(prices_raw, str):
            prices_raw = json.loads(prices_raw)
        prices = [float(p) for p in prices_raw]
        for i, price in enumerate(prices):
            if price >= 0.99:
                return outcomes[i] if i < len(outcomes) else ("YES" if i == 0 else "NO")
        return None
    except Exception as e:
        print(f"[settle] resolution fetch failed for {market_id}: {e}")
        return None


def settle_trade(trade_id, session):
    trade = session.get(PaperTrade, trade_id)
    if not trade:
        raise ValueError(f"Trade {trade_id} not found.")
    if trade.status != "OPEN":
        return {"trade_id": trade_id, "status": trade.status,
                "pnl": trade.pnl, "message": "Already settled."}

    resolution = _get_market_resolution(trade.market_id)

    if resolution is None:
        age_days = (datetime.utcnow() - trade.created_at).days
        if age_days < 7:
            return {"trade_id": trade_id, "status": "OPEN",
                    "pnl": None, "message": "Market not resolved yet."}
        market = session.get(Market, str(trade.market_id))
        if market:
            current_price = float(market.current_odds) if trade.outcome == "YES" \
                            else round(1.0 - float(market.current_odds), 6)
            payout = round(trade.shares * current_price, 6)
        else:
            payout = 0.0
        pnl    = round(payout - trade.total_cost, 6)
        result = "EXPIRED"
    else:
        won = (trade.outcome == resolution)
        payout = round(trade.shares * 1.0, 6) if won else 0.0
        pnl    = round(payout - trade.total_cost, 6)
        result = "WIN" if won else "LOSS"

    trade.status    = "CLOSED"
    trade.pnl       = pnl
    trade.closed_at = datetime.utcnow()
    session.add(trade)

    config = session.exec(
        select(WalletConfig).where(WalletConfig.telegram_user_id == trade.telegram_user_id)
    ).first()
    if config and payout > 0:
        config.paper_balance = round(config.paper_balance + payout, 6)
        config.updated_at    = datetime.utcnow()
        session.add(config)

    session.commit()

    return {
        "trade_id": trade_id, "market_id": trade.market_id,
        "market_question": trade.market_question, "your_bet": trade.outcome,
        "market_resolved": resolution, "result": result,
        "shares": trade.shares, "cost": trade.total_cost,
        "payout": payout, "pnl": pnl,
        "status": "CLOSED", "closed_at": trade.closed_at.isoformat(),
    }


def settle_all_open_trades(telegram_user_id, session):
    open_trades = session.exec(
        select(PaperTrade).where(
            PaperTrade.telegram_user_id == str(telegram_user_id),
            PaperTrade.status == "OPEN",
        )
    ).all()
    return [settle_trade(t.id, session) for t in open_trades]


# ─── WALLET SUMMARY ──────────────────────────────────────────────────────────

def get_wallet_summary(session, wallet_address=None, telegram_user_id=None):
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
    mode   = getattr(config, 'trading_mode', 'paper')

    # ── Real mode: read from RealTrade table ─────────────────────────────────
    if mode == "real":
        from services.backend.data.models import RealTrade
        raw_trades    = session.exec(
            select(RealTrade)
            .where(RealTrade.telegram_user_id == str(telegram_user_id))
            .order_by(RealTrade.created_at.desc())
        ).all()
        open_trades   = [t for t in raw_trades if t.status not in ("closed", "failed")]
        closed_trades = [t for t in raw_trades if t.status == "closed"]
        wins          = [t for t in closed_trades if (t.pnl or 0) > 0]
        losses        = [t for t in closed_trades if (t.pnl or 0) < 0]
        open_cost     = round(sum(t.total_cost_usdc for t in open_trades), 2)
        balance       = round(config.real_balance_usdc, 2)
        total_val     = round(balance + open_cost, 2)
        deposited     = 1000.0
        net_pnl       = round(total_val - deposited, 2)
        net_pnl_pct   = round((net_pnl / deposited) * 100, 2) if deposited else 0
        win_rate      = round((len(wins) / len(closed_trades)) * 100, 1) if closed_trades else 0.0

        def _real_trade_dict(t):
            return {
                "id": t.id, "market_id": t.market_id,
                "market_question": t.market_question,
                "outcome": t.outcome, "direction": "BUY",
                "shares": t.shares, "price_per_share": t.price_per_share,
                "total_cost": t.total_cost_usdc,
                "status": t.status.upper() if t.status else "OPEN",
                "result": "WIN" if (t.pnl or 0) > 0 else "LOSS" if (t.pnl or 0) < 0 else "OPEN",
                "current_price": None, "current_value": None, "unrealized_pnl": None,
                "pnl": t.pnl, "pnl_display": _fmt_pnl(t.pnl),
                "tx_hash": t.polygon_tx_hash,
                "closed_at": t.settled_at.isoformat() if t.settled_at else None,
                "created_at": t.created_at.isoformat(),
            }

        return {
            "wallet_address":        wallet_address,
            "telegram_user_id":      telegram_user_id,
            "trading_mode":          "real",
            "paper_balance":         round(config.paper_balance, 2),
            "real_balance_usdc":     balance,
            "open_positions_cost":   open_cost,
            "total_portfolio_value": total_val,
            "net_pnl":               net_pnl,
            "net_pnl_pct":           net_pnl_pct,
            "total_trades":          len(raw_trades),
            "open_trades_count":     len(open_trades),
            "closed_trades_count":   len(closed_trades),
            "wins":                  len(wins),
            "losses":                len(losses),
            "win_rate_pct":          win_rate,
            "trades":                [_real_trade_dict(t) for t in raw_trades],
        }

    # ── Paper mode (original behaviour) ──────────────────────────────────────
    settle_all_open_trades(telegram_user_id, session)
    config = _ensure_wallet_config(telegram_user_id, session)  # re-fetch after settle

    trades = session.exec(
        select(PaperTrade)
        .where(PaperTrade.telegram_user_id == str(telegram_user_id))
        .order_by(PaperTrade.created_at.desc())
    ).all()

    open_trades   = [t for t in trades if t.status == "OPEN"]
    closed_trades = [t for t in trades if t.status == "CLOSED"]
    wins          = [t for t in closed_trades if (t.pnl or 0) > 0]
    losses        = [t for t in closed_trades if (t.pnl or 0) < 0]

    open_cost   = round(sum(t.total_cost for t in open_trades), 2)
    total_val   = round(config.paper_balance + open_cost, 2)
    net_pnl     = round(total_val - config.total_deposited, 2)
    net_pnl_pct = round((net_pnl / config.total_deposited) * 100, 2) if config.total_deposited else 0
    win_rate    = round((len(wins) / len(closed_trades)) * 100, 1) if closed_trades else 0.0

    def _open_trade_dict(t):
        market = session.get(Market, str(t.market_id))
        if market:
            cur_price = float(market.current_odds) if t.outcome == "YES" \
                        else round(1.0 - float(market.current_odds), 6)
        else:
            cur_price = t.price_per_share
        cur_price = min(0.99, max(0.01, cur_price))
        cur_value = round(t.shares * cur_price, 2)
        unr_pnl   = round(cur_value - t.total_cost, 2)
        return {
            "id": t.id, "market_id": t.market_id,
            "market_question": t.market_question,
            "outcome": t.outcome, "direction": t.direction,
            "shares": t.shares, "price_per_share": t.price_per_share,
            "total_cost": t.total_cost, "status": t.status, "result": "OPEN",
            "current_price": cur_price, "current_value": cur_value,
            "unrealized_pnl": unr_pnl, "pnl": unr_pnl,
            "pnl_display": _fmt_pnl(unr_pnl),
            "tx_hash": t.tx_hash, "closed_at": None,
            "created_at": t.created_at.isoformat(),
        }

    def _closed_trade_dict(t):
        return {
            "id": t.id, "market_id": t.market_id,
            "market_question": t.market_question,
            "outcome": t.outcome, "direction": t.direction,
            "shares": t.shares, "price_per_share": t.price_per_share,
            "total_cost": t.total_cost, "status": t.status,
            "result": _result_label(t),
            "current_price": None, "current_value": None, "unrealized_pnl": None,
            "pnl": t.pnl, "pnl_display": _fmt_pnl(t.pnl),
            "tx_hash": t.tx_hash,
            "closed_at": t.closed_at.isoformat() if t.closed_at else None,
            "created_at": t.created_at.isoformat(),
        }

    return {
        "wallet_address":        wallet_address,
        "telegram_user_id":      telegram_user_id,
        "trading_mode":          config.trading_mode,
        "paper_balance":         round(config.paper_balance, 2),
        "real_balance_usdc":     round(config.real_balance_usdc, 2),
        "open_positions_cost":   open_cost,
        "total_portfolio_value": total_val,
        "net_pnl":               net_pnl,
        "net_pnl_pct":           net_pnl_pct,
        "total_trades":          len(trades),
        "open_trades_count":     len(open_trades),
        "closed_trades_count":   len(closed_trades),
        "wins":                  len(wins),
        "losses":                len(losses),
        "win_rate_pct":          win_rate,
        "trades": [_open_trade_dict(t) for t in open_trades] +
                  [_closed_trade_dict(t) for t in closed_trades],
    }


def _result_label(t):
    if t.status != "CLOSED": return "OPEN"
    if (t.pnl or 0) > 0:    return "WIN"
    if (t.pnl or 0) < 0:    return "LOSS"
    return "BREAK_EVEN"


def _fmt_pnl(pnl):
    if pnl is None: return None
    return f"+${pnl:.2f}" if pnl >= 0 else f"-${abs(pnl):.2f}"


# ─── TESTNET COMMIT ──────────────────────────────────────────────────────────

def commit_trade_to_testnet(trade_id, session):
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
