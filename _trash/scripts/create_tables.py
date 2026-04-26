"""
create_tables.py — Force creates all missing tables directly via SQL.
Run with: python create_tables.py
No import dependency issues — uses raw SQL only.
"""
import os
from dotenv import load_dotenv
load_dotenv(override=True)

from sqlalchemy import create_engine, text

url = os.getenv("DATABASE_URL", "").strip()
if url.startswith("postgres://"):
    url = url.replace("postgres://", "postgresql://", 1)
for junk in ["&channel_binding=require", "channel_binding=require&", "?channel_binding=require"]:
    url = url.replace(junk, "")

engine = create_engine(url, echo=False)

TABLES = [
    ("audit_logs", """
        CREATE TABLE IF NOT EXISTS audit_logs (
            id SERIAL PRIMARY KEY,
            telegram_user_id VARCHAR,
            action VARCHAR NOT NULL DEFAULT 'advice',
            market_id VARCHAR,
            premium BOOLEAN NOT NULL DEFAULT FALSE,
            success BOOLEAN NOT NULL DEFAULT TRUE,
            response_time_ms INTEGER,
            outcome_correct BOOLEAN,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """),
    ("user_permissions", """
        CREATE TABLE IF NOT EXISTS user_permissions (
            id SERIAL PRIMARY KEY,
            telegram_user_id VARCHAR NOT NULL UNIQUE,
            auto_trade_enabled BOOLEAN NOT NULL DEFAULT FALSE,
            trade_mode VARCHAR NOT NULL DEFAULT 'paper',
            max_bet_size FLOAT NOT NULL DEFAULT 10.0,
            min_confidence FLOAT NOT NULL DEFAULT 0.75,
            preferred_language VARCHAR NOT NULL DEFAULT 'en',
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """),
    ("conversations", """
        CREATE TABLE IF NOT EXISTS conversations (
            id SERIAL PRIMARY KEY,
            telegram_user_id VARCHAR NOT NULL,
            market_id VARCHAR NOT NULL,
            messages JSONB NOT NULL DEFAULT '[]',
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """),
    ("pending_trades", """
        CREATE TABLE IF NOT EXISTS pending_trades (
            id SERIAL PRIMARY KEY,
            telegram_user_id VARCHAR NOT NULL,
            market_id VARCHAR NOT NULL,
            market_question VARCHAR NOT NULL,
            suggested_plan VARCHAR NOT NULL,
            confidence FLOAT NOT NULL,
            amount_usdc FLOAT NOT NULL,
            status VARCHAR NOT NULL DEFAULT 'pending',
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            expires_at TIMESTAMP NOT NULL,
            confirmed_at TIMESTAMP
        )
    """),
    ("alert_history", """
        CREATE TABLE IF NOT EXISTS alert_history (
            id SERIAL PRIMARY KEY,
            telegram_user_id VARCHAR NOT NULL,
            market_id VARCHAR NOT NULL,
            score FLOAT NOT NULL,
            sent_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """),
]

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_audit_logs_user ON audit_logs(telegram_user_id)",
    "CREATE INDEX IF NOT EXISTS idx_audit_logs_created ON audit_logs(created_at)",
    "CREATE INDEX IF NOT EXISTS idx_conversations_user ON conversations(telegram_user_id)",
    "CREATE INDEX IF NOT EXISTS idx_conversations_market ON conversations(market_id)",
    "CREATE INDEX IF NOT EXISTS idx_pending_trades_user ON pending_trades(telegram_user_id)",
    "CREATE INDEX IF NOT EXISTS idx_alert_history_user ON alert_history(telegram_user_id)",
    "CREATE INDEX IF NOT EXISTS idx_alert_history_market ON alert_history(market_id)",
]

print("\n🔨 Creating missing tables...\n")
with engine.connect() as conn:
    for name, ddl in TABLES:
        try:
            conn.execute(text(ddl))
            conn.commit()
            print(f"  ✅ {name} — created (or already existed)")
        except Exception as e:
            print(f"  ❌ {name} — ERROR: {e}")
            conn.rollback()

    print("\n🔨 Creating indexes...\n")
    for idx in INDEXES:
        try:
            conn.execute(text(idx))
            conn.commit()
            print(f"  ✅ {idx.split('idx_')[1].split(' ')[0]}")
        except Exception as e:
            print(f"  ❌ Index error: {e}")
            conn.rollback()

# ── Verify ────────────────────────────────────────────────────
from sqlalchemy import inspect
existing = set(inspect(engine).get_table_names())
expected = {"audit_logs", "user_permissions", "conversations", "pending_trades", "alert_history"}
missing  = expected - existing

print("\n📋 Verification:")
for t in sorted(expected):
    status = "✅" if t in existing else "❌ STILL MISSING"
    print(f"  {status} {t}")

if missing:
    print(f"\n❌ {len(missing)} tables still missing: {missing}")
    print("   → Check Neon DB permissions or try running from the Neon SQL editor directly.")
else:
    print("\n✅ All 5 tables confirmed in Neon!")
    print("\n👉 Now restart your backend server:")
    print("   uvicorn services.backend.main:app --reload --port 8000")
