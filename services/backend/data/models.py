from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime

# 1. User Table
class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    wallet_address: str = Field(unique=True, index=True)
    telegram_id: Optional[str] = Field(default=None, unique=True)
    username: Optional[str] = Field(default=None)
    privy_user_id: Optional[str] = Field(default=None, index=True)  # Privy DID
    created_at: datetime = Field(default_factory=datetime.utcnow)

    payments: List["Payment"] = Relationship(back_populates="user")
    trades: List["Trade"] = Relationship(back_populates="user")

# 2. Market Table
class Market(SQLModel, table=True):
    id: str = Field(primary_key=True)
    question: str
    category: str
    current_odds: float
    previous_odds: float = Field(default=0.5)
    volume: float = Field(default=0.0)
    avg_volume: float = Field(default=0.0)
    is_active: bool = Field(default=True)
    expires_at: datetime

    signals: List["AISignal"] = Relationship(back_populates="market")
    trades: List["Trade"] = Relationship(back_populates="market")

# 3. AISignal Table
class AISignal(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    market_id: str = Field(foreign_key="market.id")
    prediction: str
    confidence_score: float
    analysis_summary: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    market: Market = Relationship(back_populates="signals")

# 4. Payment Table (x402)
class Payment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    market_id: str = Field(foreign_key="market.id")
    amount: float
    tx_hash: str = Field(unique=True)
    is_confirmed: bool = Field(default=False)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    user: User = Relationship(back_populates="payments")

# 5. Trade Table
class Trade(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    market_id: str = Field(foreign_key="market.id")
    outcome_selected: str
    bet_amount: float
    odds_at_time: float
    status: str = Field(default="Open")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    user: User = Relationship(back_populates="trades")
    market: Market = Relationship(back_populates="trades")

# 6. PaperTrade Table
class PaperTrade(SQLModel, table=True):
    """Stores all paper trades. No real money is ever moved."""
    __tablename__ = "paper_trades"

    id: Optional[int] = Field(default=None, primary_key=True)
    telegram_user_id: str = Field(index=True)
    market_id: str
    market_question: str
    outcome: str                     # "YES" or "NO"
    shares: float
    price_per_share: float           # e.g. 0.65 (65 cents on the dollar)
    total_cost: float                # shares * price_per_share
    direction: str                   # "BUY" or "SELL"
    status: str = Field(default="OPEN")   # OPEN | CLOSED | CANCELLED
    tx_hash: Optional[str] = None    # Polygon testnet receipt (optional)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    closed_at: Optional[datetime] = None
    pnl: Optional[float] = None      # Filled when trade is closed

# 7. LeaderboardSnapshot Table
class LeaderboardSnapshot(SQLModel, table=True):
    """Daily snapshot of each user's leaderboard stats."""
    __tablename__ = "leaderboard_snapshots"

    id: Optional[int] = Field(default=None, primary_key=True)
    telegram_user_id: str = Field(index=True)
    display_name: Optional[str] = None
    portfolio_value: float = Field(default=1000.0)
    net_pnl: float = Field(default=0.0)
    total_trades: int = Field(default=0)
    win_rate: float = Field(default=0.0)   # 0-100
    snapshot_date: datetime = Field(default_factory=datetime.utcnow)

# 8. WalletConfig Table  ← extended for Phase 1
class WalletConfig(SQLModel, table=True):
    """
    Per-user wallet settings, balances, and trading mode.

    trading_mode:    'paper' (default) | 'real'
                     The backend always checks this before executing any trade.
                     Frontend sends intent; this field determines the code path.

    kyc_status:      'none' | 'pending' | 'approved' | 'rejected'
                     Must be 'approved' before switching to real trading mode.
                     For MVP, set to 'approved' manually or via a simple phone check.

    real_balance_usdc:  Cached on-chain USDC balance on Base (in dollars).
                        Updated by Privy webhook (funds.deposited) and manual sync.
                        Must be >= 10.0 to unlock real trading mode.

    privy_user_id:   Privy DID string (did:privy:...) — stored here for
                     server-side Privy API calls (balance sync, session checks).
    """
    __tablename__ = "wallet_config"

    id: Optional[int] = Field(default=None, primary_key=True)
    telegram_user_id: str = Field(index=True, unique=True)

    # ── Paper trading (original fields) ─────────────────────────────────────
    paper_balance: float = Field(default=1000.0)
    total_deposited: float = Field(default=1000.0)

    # ── Trading mode ─────────────────────────────────────────────────────────
    trading_mode: str = Field(default="paper")      # 'paper' | 'real'

    # ── KYC ──────────────────────────────────────────────────────────────────
    kyc_status: str = Field(default="none")         # 'none'|'pending'|'approved'|'rejected'

    # ── Real on-chain balance (Phase 2+) ─────────────────────────────────────
    real_balance_usdc: float = Field(default=0.0)   # cached USDC on Base
    last_balance_sync: Optional[datetime] = None     # when real_balance_usdc was last updated

    # ── Privy identity ───────────────────────────────────────────────────────
    privy_user_id: Optional[str] = Field(default=None, index=True)

    # ── Timestamps ───────────────────────────────────────────────────────────
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
