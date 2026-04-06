import os
from sqlmodel import SQLModel, Session, create_engine
from sqlalchemy import text

# Import ALL models so SQLModel registers every table with create_all()
from services.backend.data.models import (
    User, Market, AISignal, Payment, Trade,
    PaperTrade, WalletConfig, LeaderboardSnapshot,
    BridgeTransaction, RealTrade, PretiumTransaction,
    User, Market, AISignal, Payment, TelegramProfile, Trade,
    PaperTrade, WalletConfig, LeaderboardSnapshot,
    Conversation, UserPermission, AuditLog,
    PendingTrade, AlertHistory, BridgeTransaction, RealTrade,
)

# ─────────────────────────────────────────────
# DATABASE URL RESOLUTION
# ─────────────────────────────────────────────

def _build_database_url() -> str:
    url = os.getenv("DATABASE_URL", "").strip()

    if url:
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        url = url.replace("&channel_binding=require", "")
        url = url.replace("channel_binding=require&", "")
        url = url.replace("?channel_binding=require", "")
        print("Database: Neon PostgreSQL")
        return url

    base_dir = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    )
    db_path = os.path.join(base_dir, "data", "assistant.db")
    print(f"Database: SQLite at {os.path.abspath(db_path)}")
    return f"sqlite:///{db_path}"


DATABASE_URL = _build_database_url()
IS_SQLITE = DATABASE_URL.startswith("sqlite")

# ─────────────────────────────────────────────
# ENGINE
# ─────────────────────────────────────────────

if IS_SQLITE:
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        echo=False,
    )
else:
    # pool_pre_ping tests connection before using to gracefully handle server-side disconnects
    # pool_recycle forces connection re-establishment every 30 minutes
    engine = create_engine(
        DATABASE_URL, 
        echo=False,
        pool_pre_ping=True,
        pool_recycle=1800
    )


# ─────────────────────────────────────────────
# MIGRATIONS
# Adds new columns to existing tables without dropping data.
# Uses IF NOT EXISTS (Postgres) or tries silently (SQLite).
# Safe to run on every startup — idempotent.
# ─────────────────────────────────────────────

# Each entry: (description, postgres_sql, sqlite_sql)
# sqlite_sql is None if SQLite syntax is the same or not needed
_COLUMN_MIGRATIONS = [
    (
        'user.privy_user_id',
        'ALTER TABLE "user" ADD COLUMN IF NOT EXISTS privy_user_id VARCHAR',
        'ALTER TABLE "user" ADD COLUMN privy_user_id VARCHAR',
    ),
    (
        'wallet_config.trading_mode',
        "ALTER TABLE wallet_config ADD COLUMN IF NOT EXISTS trading_mode VARCHAR NOT NULL DEFAULT 'paper'",
        "ALTER TABLE wallet_config ADD COLUMN trading_mode VARCHAR NOT NULL DEFAULT 'paper'",
    ),
    (
        'wallet_config.kyc_status',
        "ALTER TABLE wallet_config ADD COLUMN IF NOT EXISTS kyc_status VARCHAR NOT NULL DEFAULT 'none'",
        "ALTER TABLE wallet_config ADD COLUMN kyc_status VARCHAR NOT NULL DEFAULT 'none'",
    ),
    (
        'wallet_config.real_balance_usdc',
        'ALTER TABLE wallet_config ADD COLUMN IF NOT EXISTS real_balance_usdc FLOAT NOT NULL DEFAULT 0.0',
        'ALTER TABLE wallet_config ADD COLUMN real_balance_usdc FLOAT NOT NULL DEFAULT 0.0',
    ),
    (
        'wallet_config.last_balance_sync',
        'ALTER TABLE wallet_config ADD COLUMN IF NOT EXISTS last_balance_sync TIMESTAMP',
        'ALTER TABLE wallet_config ADD COLUMN last_balance_sync TIMESTAMP',
    ),
    (
        'wallet_config.privy_user_id',
        'ALTER TABLE wallet_config ADD COLUMN IF NOT EXISTS privy_user_id VARCHAR',
        'ALTER TABLE wallet_config ADD COLUMN privy_user_id VARCHAR',
    ),
    # nort_user_id — integer FK to user.id — added to all identity tables
    (
        'conversations.nort_user_id',
        'ALTER TABLE conversations ADD COLUMN IF NOT EXISTS nort_user_id INTEGER REFERENCES "user"(id)',
        'ALTER TABLE conversations ADD COLUMN nort_user_id INTEGER',
    ),
    (
        'wallet_config.nort_user_id',
        'ALTER TABLE wallet_config ADD COLUMN IF NOT EXISTS nort_user_id INTEGER REFERENCES "user"(id)',
        'ALTER TABLE wallet_config ADD COLUMN nort_user_id INTEGER',
    ),
    (
        'user_permissions.nort_user_id',
        'ALTER TABLE user_permissions ADD COLUMN IF NOT EXISTS nort_user_id INTEGER REFERENCES "user"(id)',
        'ALTER TABLE user_permissions ADD COLUMN nort_user_id INTEGER',
    ),
    (
        'paper_trades.nort_user_id',
        'ALTER TABLE paper_trades ADD COLUMN IF NOT EXISTS nort_user_id INTEGER REFERENCES "user"(id)',
        'ALTER TABLE paper_trades ADD COLUMN nort_user_id INTEGER',
    ),
    (
        'audit_logs.nort_user_id',
        'ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS nort_user_id INTEGER REFERENCES "user"(id)',
        'ALTER TABLE audit_logs ADD COLUMN nort_user_id INTEGER',
    ),
]


def _run_migrations():
    """
    Apply column migrations. Postgres uses IF NOT EXISTS so it's a no-op
    when columns already exist. SQLite swallows the duplicate column error.
    """
    with engine.connect() as conn:
        for name, pg_sql, sqlite_sql in _COLUMN_MIGRATIONS:
            sql = sqlite_sql if IS_SQLITE else pg_sql
            try:
                conn.execute(text(sql))
                conn.commit()
                print(f"[migration] OK  {name}")
            except Exception as e:
                err = str(e).lower()
                # SQLite raises "duplicate column" — that just means it already exists
                if "duplicate column" in err or "already exists" in err:
                    print(f"[migration] already exists  {name}")
                else:
                    print(f"[migration] ERROR {name}: {e}")
                conn.rollback()


# ─────────────────────────────────────────────
# INIT
# ─────────────────────────────────────────────

def init_db():
    """
    1. Create all tables that don't exist yet (SQLModel create_all).
    2. Apply column migrations for tables that already exist.
    Safe to call on every startup.
    """
    SQLModel.metadata.create_all(engine)
    print("Database tables ready.")
    _run_migrations()
    print("Database migrations complete.")


def get_session():
    """FastAPI dependency that provides a database session."""
    with Session(engine) as session:
        yield session


if __name__ == "__main__":
    print("Building database tables...")
    init_db()
    print("Done.")
