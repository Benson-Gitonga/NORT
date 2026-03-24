"""
Migration: Add Phase 2 tables and columns to Neon PostgreSQL.

New:
  - bridge_transactions table  (LI.FI bridge tracking)
  - real_trades table          (real on-chain trade history)
  - wallet_config.trading_mode
  - wallet_config.real_balance_usdc
  - wallet_config.last_balance_sync

Uses CREATE TABLE IF NOT EXISTS + ADD COLUMN IF NOT EXISTS — fully idempotent.
"""

import os
import psycopg2

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://neondb_owner:npg_6Wi2jAceFoBa@ep-crimson-recipe-ai22kk5i-pooler.c-4.us-east-1.aws.neon.tech/neondb?sslmode=require"
).replace("postgres://", "postgresql://", 1)

def run():
    print("Connecting to Neon...")
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    cur = conn.cursor()

    # ── wallet_config: new columns ────────────────────────────────────────────
    wallet_cols = [
        ("trading_mode",      "ALTER TABLE wallet_config ADD COLUMN IF NOT EXISTS trading_mode TEXT NOT NULL DEFAULT 'paper'"),
        ("real_balance_usdc", "ALTER TABLE wallet_config ADD COLUMN IF NOT EXISTS real_balance_usdc FLOAT NOT NULL DEFAULT 0.0"),
        ("last_balance_sync", "ALTER TABLE wallet_config ADD COLUMN IF NOT EXISTS last_balance_sync TIMESTAMP"),
    ]
    print("\n── wallet_config columns ──")
    for col, sql in wallet_cols:
        try:
            cur.execute(sql)
            print(f"  OK   wallet_config.{col}")
        except Exception as e:
            print(f"  ERR  wallet_config.{col} — {e}")

    # ── bridge_transactions table ─────────────────────────────────────────────
    print("\n── bridge_transactions table ──")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS bridge_transactions (
            id                     SERIAL PRIMARY KEY,
            telegram_user_id       TEXT NOT NULL,
            wallet_address         TEXT NOT NULL,
            amount_usdc            FLOAT NOT NULL,
            from_chain             TEXT NOT NULL DEFAULT 'BASE',
            to_chain               TEXT NOT NULL DEFAULT 'POL',
            lifi_tx_hash           TEXT,
            lifi_receiving_tx_hash TEXT,
            lifi_tool              TEXT,
            status                 TEXT NOT NULL DEFAULT 'pending',
            error_message          TEXT,
            real_trade_id          INTEGER,
            created_at             TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at             TIMESTAMP NOT NULL DEFAULT NOW(),
            completed_at           TIMESTAMP
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_bridge_user ON bridge_transactions(telegram_user_id)")
    print("  OK   bridge_transactions")

    # ── real_trades table ─────────────────────────────────────────────────────
    print("\n── real_trades table ──")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS real_trades (
            id                   SERIAL PRIMARY KEY,
            telegram_user_id     TEXT NOT NULL,
            wallet_address       TEXT NOT NULL,
            market_id            TEXT NOT NULL,
            market_question      TEXT NOT NULL,
            outcome              TEXT NOT NULL,
            shares               FLOAT NOT NULL,
            price_per_share      FLOAT NOT NULL,
            total_cost_usdc      FLOAT NOT NULL,
            bridge_tx_id         INTEGER,
            bridged_amount_usdc  FLOAT NOT NULL DEFAULT 0.0,
            polymarket_order_id  TEXT,
            polygon_tx_hash      TEXT,
            status               TEXT NOT NULL DEFAULT 'pending_bridge',
            pnl                  FLOAT,
            settled_at           TIMESTAMP,
            error_message        TEXT,
            created_at           TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at           TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_realtrade_user ON real_trades(telegram_user_id)")
    print("  OK   real_trades")

    # ── Verification ─────────────────────────────────────────────────────────
    print("\n── Verification ──")
    checks = [
        ("wallet_config",       "trading_mode"),
        ("wallet_config",       "real_balance_usdc"),
        ("bridge_transactions", None),
        ("real_trades",         None),
    ]
    for table, col in checks:
        if col:
            cur.execute(f"""
                SELECT COUNT(*) FROM information_schema.columns
                WHERE table_name='{table}' AND column_name='{col}'
            """)
            exists = cur.fetchone()[0] > 0
        else:
            cur.execute(f"""
                SELECT COUNT(*) FROM information_schema.tables
                WHERE table_name='{table}'
            """)
            exists = cur.fetchone()[0] > 0
        label = f"{table}.{col}" if col else table
        print(f"  {'EXISTS' if exists else 'MISSING':8s} {label}")

    cur.close()
    conn.close()
    print("\nMigration complete.")

if __name__ == "__main__":
    run()
