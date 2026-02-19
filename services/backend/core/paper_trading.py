"""
Core paper trading logic for Polymarket AI Assistant.
Intern 5 - Paper Trading & Wallet

Uses the shared models:
  - User          (wallet_address + telegram_id)
  - WalletConfig  (paper balance, keyed by telegram_user_id)
  - PaperTrade    (trades, keyed by telegram_user_id)

Real wallet address lives in User.
Paper balance and trades are linked via telegram_user_id.
No real USDC ever moves.
"""

import hashlib
import time
from datetime import datetime
from typing import Optional
from sqlmodel import Session, select

# Use the SHARED team models
from services.backend.data.models import User, WalletConfig, PaperTrade


# ─────────────────────────────────────────────
# USER / WALLET HELPERS
# ─────────────────────────────────────────────

def connect_wallet(
    wallet_address: str,
    session: Session,
    telegram_id: Optional[str] = None,
    username: Optional[str] = None,
) -> User:
    """
    Register a real MetaMask wallet address into the system.
    - New wallet → creates User + WalletConfig with 1000 paper USDC
    - Existing wallet → updates telegram_id if provided
    """
    wallet_address = wallet_address.lower()

    statement = select(User).where(User.wallet_address == wallet_address)
    user = session.exec(statement).first()

    if not user:
        user = User(
            wallet_address=wallet_address,
            telegram_id=telegram_id,
            username=username,
        )
        session.add(user)
        session.commit()
        session.refresh(user)

        if telegram_id:
            _ensure_wallet_config(telegram_id, session)
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

        if user.telegram_id:
            _ensure_wallet_config(user.telegram_id, session)

    return user


def _ensure_wallet_config(telegram_user_id: str, session: Session) -> WalletConfig:
    """Create a WalletConfig with 1000 paper USDC if one doesn't exist."""
    statement = select(WalletConfig).where(
        WalletConfig.telegram_user_id == str(telegram_user_id)
    )
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
# WALLET SUMMARY
# ─────────────────────────────────────────────

def get_wallet_summary(
    session: Session,
    wallet_address: Optional[str] = None,
    telegram_user_id: Optional[str] = None,
) -> dict:
    """
    Return full paper wallet summary. Accepts wallet_address OR telegram_user_id.
    Used by: GET /wallet/summary, OpenClaw skill, Telegram /portfolio
    """
    if wallet_address and not telegram_user_id:
        user = get_user_by_wallet(wallet_address, session)
        if not user:
            raise ValueError(f"Wallet {wallet_address} not found. Connect it first.")
        if not user.telegram_id:
            raise ValueError(
                f"Wallet {wallet_address} has no linked Telegram ID yet. "
                "Link your Telegram account to see your paper balance."
            )
        telegram_user_id = user.telegram_id
        wallet_address = user.wallet_address
    elif telegram_user_id and not wallet_address:
        user = get_user_by_telegram(telegram_user_id, session)
        wallet_address = user.wallet_address if user else None

    if not telegram_user_id:
        raise ValueError("Could not resolve a telegram_user_id.")

    config_stmt = select(WalletConfig).where(
        WalletConfig.telegram_user_id == str(telegram_user_id)
    )
    config = session.exec(config_stmt).first()

    if not config:
        raise ValueError(
            f"No paper wallet for Telegram user {telegram_user_id}. Connect a wallet first."
        )

    trades_stmt = select(PaperTrade).where(
        PaperTrade.telegram_user_id == str(telegram_user_id)
    )
    trades = session.exec(trades_stmt).all()

    open_trades = [t for t in trades if t.status == "OPEN"]
    closed_trades = [t for t in trades if t.status == "CLOSED"]
    total_realized_pnl = sum(t.pnl or 0.0 for t in closed_trades)
    open_positions_cost = sum(t.total_cost for t in open_trades)
    total_value = round(config.paper_balance + open_positions_cost, 2)
    net_pnl = round(total_value - config.total_deposited + total_realized_pnl, 2)

    return {
        "wallet_address": wallet_address,
        "telegram_user_id": telegram_user_id,
        "paper_balance": round(config.paper_balance, 2),
        "open_positions_cost": round(open_positions_cost, 2),
        "total_portfolio_value": total_value,
        "total_realized_pnl": round(total_realized_pnl, 2),
        "net_pnl": net_pnl,
        "total_trades": len(trades),
        "open_trades_count": len(open_trades),
        "closed_trades_count": len(closed_trades),
        "trades": [
            {
                "id": t.id,
                "market_id": t.market_id,
                "market_question": t.market_question,
                "outcome": t.outcome,
                "direction": t.direction,
                "shares": t.shares,
                "price_per_share": t.price_per_share,
                "total_cost": t.total_cost,
                "status": t.status,
                "pnl": t.pnl,
                "tx_hash": t.tx_hash,
                "created_at": t.created_at.isoformat(),
            }
            for t in trades
        ],
    }


# ─────────────────────────────────────────────
# PAPER TRADING
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
    """
    Place a paper trade for a user identified by telegram_user_id.
    Deducts total_cost from paper balance for BUY trades.
    """
    telegram_user_id = str(telegram_user_id)

    if outcome.upper() not in ("YES", "NO"):
        raise ValueError("Outcome must be 'YES' or 'NO'.")
    if direction.upper() not in ("BUY", "SELL"):
        raise ValueError("Direction must be 'BUY' or 'SELL'.")
    if not (0 < price_per_share < 1):
        raise ValueError("price_per_share must be between 0 and 1 (e.g. 0.65).")
    if shares <= 0:
        raise ValueError("Shares must be greater than 0.")

    total_cost = round(shares * price_per_share, 6)

    if total_cost < 1.0:
        raise ValueError("Minimum trade value is 1 paper USDC (shares x price must be >= 1).")

    config_stmt = select(WalletConfig).where(
        WalletConfig.telegram_user_id == telegram_user_id
    )
    config = session.exec(config_stmt).first()

    if not config:
        raise ValueError(
            f"No paper wallet for Telegram user {telegram_user_id}. "
            "Connect a wallet first via POST /wallet/connect."
        )

    if direction.upper() == "BUY" and config.paper_balance < total_cost:
        raise ValueError(
            f"Insufficient paper balance. "
            f"You have ${config.paper_balance:.2f}, trade costs ${total_cost:.2f}."
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
# OPTIONAL: TESTNET COMMIT
# ─────────────────────────────────────────────

def commit_trade_to_testnet(trade_id: int, session: Session) -> str:
    """Attach a mock Polygon testnet tx hash to a paper trade."""
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