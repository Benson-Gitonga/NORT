"""
migrate_user_id.py — Add user_id column to all agent tables.

Strategy:
  1. Add user_id column (nullable initially)
  2. Backfill: user_id = telegram_user_id for existing rows
  3. Add indexes on user_id
  4. Drop the NOT NULL constraint isn't needed — user_id stays nullable
     for rows where we had no identifier at all (anonymous).

Safe to run multiple times (all DDL uses IF NOT EXISTS / DO NOTHING).
Run with: python migrate_user_id.py
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

# Each tuple: (description, SQL)
MIGRATIONS = [
    # ── user_permissions ──────────────────────────────────────────────────
    ("user_permissions: add user_id column",
     "ALTER TABLE user_permissions ADD COLUMN IF NOT EXISTS user_id VARCHAR"),
    ("user_permissions: backfill user_id from telegram_user_id",
     "UPDATE user_permissions SET user_id = telegram_user_id WHERE user_id IS NULL AND telegram_user_id IS NOT NULL"),
    ("user_permissions: unique index on user_id",
     "CREATE UNIQUE INDEX IF NOT EXISTS idx_user_permissions_user_id ON user_permissions(user_id)"),

    # ── conversations ────────────────────────────────────────────────────
    ("conversations: add user_id column",
     "ALTER TABLE conversations ADD COLUMN IF NOT EXISTS user_id VARCHAR"),
    ("conversations: backfill user_id",
     "UPDATE conversations SET user_id = telegram_user_id WHERE user_id IS NULL AND telegram_user_id IS NOT NULL"),
    ("conversations: index on user_id",
     "CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id)"),

    # ── audit_logs ───────────────────────────────────────────────────────
    ("audit_logs: add user_id column",
     "ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS user_id VARCHAR"),
    ("audit_logs: backfill user_id",
     "UPDATE audit_logs SET user_id = telegram_user_id WHERE user_id IS NULL AND telegram_user_id IS NOT NULL"),
    ("audit_logs: index on user_id",
     "CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs(user_id)"),

    # ── paper_trades ─────────────────────────────────────────────────────
    ("paper_trades: add user_id column",
     "ALTER TABLE paper_trades ADD COLUMN IF NOT EXISTS user_id VARCHAR"),
    ("paper_trades: backfill user_id",
     "UPDATE paper_trades SET user_id = telegram_user_id WHERE user_id IS NULL AND telegram_user_id IS NOT NULL"),
    ("paper_trades: index on user_id",
     "CREATE INDEX IF NOT EXISTS idx_paper_trades_user_id ON paper_trades(user_id)"),

    # ── wallet_config ─────────────────────────────────────────────────────
    ("wallet_config: add user_id column",
     "ALTER TABLE wallet_config ADD COLUMN IF NOT EXISTS user_id VARCHAR"),
    ("wallet_config: backfill user_id",
     "UPDATE wallet_config SET user_id = telegram_user_id WHERE user_id IS NULL AND telegram_user_id IS NOT NULL"),
    ("wallet_config: unique index on user_id",
     "CREATE UNIQUE INDEX IF NOT EXISTS idx_wallet_config_user_id ON wallet_config(user_id)"),

    # ── leaderboard_snapshots ─────────────────────────────────────────────
    ("leaderboard_snapshots: add user_id column",
     "ALTER TABLE leaderboard_snapshots ADD COLUMN IF NOT EXISTS user_id VARCHAR"),
    ("leaderboard_snapshots: backfill user_id",
     "UPDATE leaderboard_snapshots SET user_id = telegram_user_id WHERE user_id IS NULL AND telegram_user_id IS NOT NULL"),
    ("leaderboard_snapshots: index on user_id",
     "CREATE INDEX IF NOT EXISTS idx_leaderboard_snapshots_user_id ON leaderboard_snapshots(user_id)"),

    # ── pending_trades ────────────────────────────────────────────────────
    ("pending_trades: add user_id column",
     "ALTER TABLE pending_trades ADD COLUMN IF NOT EXISTS user_id VARCHAR"),
    ("pending_trades: backfill user_id",
     "UPDATE pending_trades SET user_id = telegram_user_id WHERE user_id IS NULL AND telegram_user_id IS NOT NULL"),
    ("pending_trades: index on user_id",
     "CREATE INDEX IF NOT EXISTS idx_pending_trades_user_id ON pending_trades(user_id)"),

    # ── alert_history ─────────────────────────────────────────────────────
    ("alert_history: add user_id column",
     "ALTER TABLE alert_history ADD COLUMN IF NOT EXISTS user_id VARCHAR"),
    ("alert_history: backfill user_id",
     "UPDATE alert_history SET user_id = telegram_user_id WHERE user_id IS NULL AND telegram_user_id IS NOT NULL"),
    ("alert_history: index on user_id",
     "CREATE INDEX IF NOT EXISTS idx_alert_history_user_id ON alert_history(user_id)"),
]

print("\n🔨 Running user_id migration...\n")
with engine.connect() as conn:
    for description, sql in MIGRATIONS:
        try:
            conn.execute(text(sql))
            conn.commit()
            print(f"  ✅ {description}")
        except Exception as e:
            err = str(e).lower()
            if "already exists" in err or "duplicate column" in err:
                print(f"  ⏭  {description} (already done)")
            else:
                print(f"  ❌ {description}\n     ERROR: {e}")
            conn.rollback()

# ── Verify ────────────────────────────────────────────────────────────────────
print("\n📋 Verification — checking user_id column exists in each table:\n")
from sqlalchemy import inspect
inspector = inspect(engine)

TABLES_TO_CHECK = [
    "user_permissions",
    "conversations",
    "audit_logs",
    "paper_trades",
    "wallet_config",
    "leaderboard_snapshots",
    "pending_trades",
    "alert_history",
]

all_ok = True
for table in TABLES_TO_CHECK:
    try:
        cols = [c["name"] for c in inspector.get_columns(table)]
        has_user_id = "user_id" in cols
        has_tg_id   = "telegram_user_id" in cols
        status = "✅" if has_user_id else "❌"
        tg_note = "(telegram_user_id kept as fallback)" if has_tg_id else "(no telegram_user_id)"
        print(f"  {status} {table}: user_id={'YES' if has_user_id else 'MISSING'} {tg_note}")
        if not has_user_id:
            all_ok = False
    except Exception as e:
        print(f"  ❌ {table}: could not inspect — {e}")
        all_ok = False

if all_ok:
    print("\n✅ Migration complete! All tables have user_id.")
    print("\n👉 Next steps:")
    print("   1. Restart your backend: uvicorn services.backend.main:app --reload --port 8000")
    print("   2. Reload the dashboard — permissions 404 should be gone")
else:
    print("\n❌ Some tables are still missing user_id — check errors above.")
