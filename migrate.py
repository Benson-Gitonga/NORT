"""
Migration: Add trading_mode and real_balance_usdc to wallet_config.

These are the ONLY two new columns needed (no KYC, no privy_user_id).
Uses ADD COLUMN IF NOT EXISTS — safe to run multiple times.
"""

import os
import psycopg2

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://neondb_owner:npg_6Wi2jAceFoBa@ep-crimson-recipe-ai22kk5i-pooler.c-4.us-east-1.aws.neon.tech/neondb?sslmode=require"
).replace("postgres://", "postgresql://", 1)

MIGRATIONS = [
    ("wallet_config", "trading_mode",      "ALTER TABLE wallet_config ADD COLUMN IF NOT EXISTS trading_mode TEXT NOT NULL DEFAULT 'paper'"),
    ("wallet_config", "real_balance_usdc", "ALTER TABLE wallet_config ADD COLUMN IF NOT EXISTS real_balance_usdc FLOAT NOT NULL DEFAULT 0.0"),
    ("wallet_config", "last_balance_sync", "ALTER TABLE wallet_config ADD COLUMN IF NOT EXISTS last_balance_sync TIMESTAMP"),
]

def run():
    print("Connecting to Neon...")
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    cur = conn.cursor()

    print("Running migrations...\n")
    for table, column, sql in MIGRATIONS:
        try:
            cur.execute(sql)
            print(f"  OK   {table}.{column}")
        except Exception as e:
            print(f"  ERR  {table}.{column} — {e}")

    print("\nVerifying...")
    for table, column, _ in MIGRATIONS:
        cur.execute(f"""
            SELECT COUNT(*) FROM information_schema.columns
            WHERE table_name = '{table}' AND column_name = '{column}'
        """)
        exists = cur.fetchone()[0] > 0
        print(f"  {'EXISTS' if exists else 'MISSING':8s} {table}.{column}")

    cur.close()
    conn.close()
    print("\nDone.")

if __name__ == "__main__":
    run()
