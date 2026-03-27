from sqlmodel import SQLModel, Field, Relationship, JSON, Column
from typing import Optional, List
from datetime import datetime

# 1. User Table
class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    wallet_address: str = Field(unique=True, index=True)
    telegram_id: Optional[str] = Field(default=None, unique=True)
    username: Optional[str] = Field(default=None)
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

# 4b. TelegramProfile Table
class TelegramProfile(SQLModel, table=True):
    __tablename__ = "telegram_profile"
    id: Optional[int] = Field(default=None, primary_key=True)
    telegram_id: str = Field(index=True, unique=True)
    user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    username: Optional[str] = None
    preferred_language: str = Field(default="en")
    pending_premium_market_id: Optional[str] = None
    auto_trade_enabled: bool = Field(default=False)
    auto_trade_limit: Optional[float] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

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
    __tablename__ = "paper_trades"
    id: Optional[int] = Field(default=None, primary_key=True)
    telegram_user_id: str = Field(index=True)
    market_id: str
    market_question: str
    outcome: str
    shares: float
    price_per_share: float
    total_cost: float
    direction: str
    status: str = Field(default="OPEN")
    tx_hash: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    closed_at: Optional[datetime] = None
    pnl: Optional[float] = None

# 7. LeaderboardSnapshot Table
class LeaderboardSnapshot(SQLModel, table=True):
    __tablename__ = "leaderboard_snapshots"
    id: Optional[int] = Field(default=None, primary_key=True)
    telegram_user_id: str = Field(index=True)
    display_name: Optional[str] = None
    portfolio_value: float = Field(default=1000.0)
    net_pnl: float = Field(default=0.0)
    total_trades: int = Field(default=0)
    win_rate: float = Field(default=0.0)
    snapshot_date: datetime = Field(default_factory=datetime.utcnow)

# 8. WalletConfig Table
class WalletConfig(SQLModel, table=True):
    __tablename__ = "wallet_config"
    id: Optional[int] = Field(default=None, primary_key=True)
    telegram_user_id: str = Field(index=True, unique=True)
    paper_balance: float = Field(default=1000.0)
    total_deposited: float = Field(default=1000.0)
    trading_mode: str = Field(default="paper")
    real_balance_usdc: float = Field(default=0.0)
    last_balance_sync: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

# 9. Conversation Table
class Conversation(SQLModel, table=True):
    __tablename__ = "conversations"
    id: Optional[int] = Field(default=None, primary_key=True)
    telegram_user_id: str = Field(index=True)
    market_id: str = Field(index=True)
    messages: list = Field(default_factory=list, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

# 10. UserPermission Table
class UserPermission(SQLModel, table=True):
    __tablename__ = "user_permissions"
    id: Optional[int] = Field(default=None, primary_key=True)
    telegram_user_id: str = Field(index=True, unique=True)
    auto_trade_enabled: bool = Field(default=False)
    trade_mode: str = Field(default="paper")   # "paper" | "real" | "confirm"
    max_bet_size: float = Field(default=10.0)
    min_confidence: float = Field(default=0.75)
    preferred_language: str = Field(default="en")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

# 11. BridgeTransaction Table
class BridgeTransaction(SQLModel, table=True):
    __tablename__ = "bridge_transactions"
    id: Optional[int] = Field(default=None, primary_key=True)
    telegram_user_id: str = Field(index=True)
    wallet_address: str
    amount_usdc: float
    from_chain: str = Field(default="BASE")
    to_chain: str = Field(default="POL")
    lifi_tx_hash: Optional[str] = None
    lifi_receiving_tx_hash: Optional[str] = None
    lifi_tool: Optional[str] = None
    status: str = Field(default="pending")
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    real_trade_id: Optional[int] = None

# 12. RealTrade Table
class RealTrade(SQLModel, table=True):
    __tablename__ = "real_trades"
    id: Optional[int] = Field(default=None, primary_key=True)
    telegram_user_id: str = Field(index=True)
    wallet_address: str
    market_id: str
    market_question: str
    outcome: str
    shares: float
    price_per_share: float
    total_cost_usdc: float
    bridge_tx_id: Optional[int] = None
    bridged_amount_usdc: float = Field(default=0.0)
    polymarket_order_id: Optional[str] = None
    polygon_tx_hash: Optional[str] = None
    status: str = Field(default="pending_bridge")
    pnl: Optional[float] = None
    settled_at: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

# 13. AuditLog Table  ← Task 4: request audit trail + rate limiting + feedback loop
class AuditLog(SQLModel, table=True):
    __tablename__ = "audit_logs"
    id: Optional[int] = Field(default=None, primary_key=True)
    telegram_user_id: Optional[str] = Field(default=None, index=True)
    action: str = Field(default="advice")
    market_id: Optional[str] = Field(default=None)
    premium: bool = Field(default=False)
    success: bool = Field(default=True)
    response_time_ms: Optional[int] = Field(default=None)
    outcome_correct: Optional[bool] = Field(default=None)   # Task 6: set on trade close
    created_at: datetime = Field(default_factory=datetime.utcnow)

# 14. PendingTrade Table  ← Task 11: confirmation flow for trade_mode="confirm"
class PendingTrade(SQLModel, table=True):
    __tablename__ = "pending_trades"
    id: Optional[int] = Field(default=None, primary_key=True)
    telegram_user_id: str = Field(index=True)
    market_id: str
    market_question: str
    suggested_plan: str       # "BUY YES" | "BUY NO"
    confidence: float
    amount_usdc: float
    status: str = Field(default="pending")   # pending|confirmed|cancelled|expired
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime                     # 10 min from created_at
    confirmed_at: Optional[datetime] = None

# 15. AlertHistory Table  ← Task 7: prevents duplicate proactive alerts
class AlertHistory(SQLModel, table=True):
    __tablename__ = "alert_history"
    id: Optional[int] = Field(default=None, primary_key=True)
    telegram_user_id: str = Field(index=True)
    market_id: str = Field(index=True)
    score: float
    sent_at: datetime = Field(default_factory=datetime.utcnow)
