"""
migrate_nort_user_id.py — Unify all tables under a real integer user.id FK.

WHAT THIS FIXES
───────────────
1. user.telegram_id was NULL for bot-only users whose wallet_address is
   'tg_XXXXXXXXX'. This extracts the real numeric Telegram ID from the
   wallet_address and writes it back to user.telegram_id.

2. Adds nort_user_id INTEGER (FK → user.id) to all tables that currently
   use a raw telegram_user_id VARCHAR string as their only identity anchor.

3. Backfills nort_user_id via two join paths:
     Path A: user.telegram_id = table.telegram_user_id          (bot users)
     Path B: telegram_profile.telegram_id = table.telegram_user_id
             → telegram_profile.user_id → user.id              (wallet users)

SAFETY
──────
- All DDL uses IF NOT EXISTS — safe to run multiple times.
- nort_user_id stays NULLABLE — rows that can't be matched are left NULL
  and logged so you can investigate manually.
- The existing telegram_user_id column is NOT dropped — backward compat.

Run with:
    python migrate_nort_user_id.py
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

# ─────────────────────────────────────────────────────────────────────────────
# STEP 1: Fix user.telegram_id for tg_XXXXXXX wallet users
# wallet_address = 'tg_7725363948' → telegram_id should be '7725363948'
# ─────────────────────────────────────────────────────────────────────────────

STEP1 = [
    (
        "user: fix telegram_id for tg_ wallet users",
        """
        UPDATE "user"
        SET telegram_id = SUBSTRING(wallet_address FROM 4)
        WHERE wallet_address LIKE 'tg_%'
          AND (telegram_id IS NULL OR telegram_id = wallet_address)
        """
    ),
]

# ─────────────────────────────────────────────────────────────────────────────
# STEP 2: Add nort_user_id INTEGER column to all affected tables
# ─────────────────────────────────────────────────────────────────────────────

TABLES = [
    "wallet_config",
    "user_permissions",
    "paper_trades",
    "real_trades",
    "conversations",
    "leaderboard_snapshots",
    "pending_trades",
    "alert_history",
    "bridge_transactions",
    "audit_logs",
]

STEP2 = []
for table in TABLES:
    STEP2.append((
        f"{table}: add nort_user_id column",
        f'ALTER TABLE {table} ADD COLUMN IF NOT EXISTS nort_user_id INTEGER REFERENCES "user"(id)',
    ))

# ─────────────────────────────────────────────────────────────────────────────
# STEP 3: Backfill nort_user_id
# Path A — direct match: user.telegram_id = table.telegram_user_id
# Path B — via telegram_profile: telegram_profile.telegram_id = table.telegram_user_id
# ─────────────────────────────────────────────────────────────────────────────

def backfill_sql(table: str, id_col: str = "telegram_user_id") -> list:
    """Returns (description, sql) tuples for Path A and Path B backfill."""
    return [
        (
            f"{table}: backfill nort_user_id via user.telegram_id (path A)",
            f"""
            UPDATE {table} t
            SET nort_user_id = u.id
            FROM "user" u
            WHERE u.telegram_id = t.{id_col}
              AND t.nort_user_id IS NULL
            """
        ),
        (
            f"{table}: backfill nort_user_id via telegram_profile (path B)",
            f"""
            UPDATE {table} t
            SET nort_user_id = tp.user_id
            FROM telegram_profile tp
            WHERE tp.telegram_id = t.{id_col}
              AND tp.user_id IS NOT NULL
              AND t.nort_user_id IS NULL
            """
        ),
    ]

STEP3 = []
for table in TABLES:
    STEP3.extend(backfill_sql(table))

# ─────────────────────────────────────────────────────────────────────────────
# STEP 4: Indexes on nort_user_id
# ─────────────────────────────────────────────────────────────────────────────

STEP4 = []
for table in TABLES:
    STEP4.append((
        f"{table}: index on nort_user_id",
        f"CREATE INDEX IF NOT EXISTS idx_{table}_nort_user_id ON {table}(nort_user_id)",
    ))

# ─────────────────────────────────────────────────────────────────────────────
# RUNNER
# ─────────────────────────────────────────────────────────────────────────────

ALL_STEPS = [
    ("STEP 1: Fix user.telegram_id for tg_ wallet users", STEP1),
    ("STEP 2: Add nort_user_id column to all tables",     STEP2),
    ("STEP 3: Backfill nort_user_id",                     STEP3),
    ("STEP 4: Create indexes",                            STEP4),
]

with engine.connect() as conn:
    for step_name, migrations in ALL_STEPS:
        print(f"\n{'─'*60}")
        print(f"  {step_name}")
        print(f"{'─'*60}")
        for description, sql in migrations:
            try:
                conn.execute(text(sql))
                conn.commit()
                print(f"  OK  {description}")
            except Exception as e:
                err = str(e).lower()
                if "already exists" in err or "duplicate column" in err:
                    print(f"  --  {description} (already done)")
                else:
                    print(f"  ERR {description}")
                    print(f"      {e}")
                conn.rollback()

# ─────────────────────────────────────────────────────────────────────────────
# VERIFICATION REPORT
# ─────────────────────────────────────────────────────────────────────────────

print(f"\n{'═'*60}")
print("  VERIFICATION REPORT")
print(f"{'═'*60}")

with engine.connect() as conn:

    # 1. Check user.telegram_id fix
    print("\n[1] user.telegram_id fix:")
    rows = conn.execute(text("""
        SELECT id, wallet_address, telegram_id
        FROM "user"
        WHERE wallet_address LIKE 'tg_%'
        ORDER BY id
    """)).fetchall()
    for r in rows:
        tg = r[2]
        expected = r[1][3:]  # strip 'tg_' prefix
        status = "OK " if tg == expected else "BAD"
        print(f"    {status}  user.id={r[0]}  wallet={r[1]}  telegram_id={tg}")

    # 2. Check nort_user_id fill rate per table
    print("\n[2] nort_user_id backfill coverage:")
    for table in TABLES:
        try:
            result = conn.execute(text(f"""
                SELECT
                    COUNT(*) AS total,
                    COUNT(nort_user_id) AS filled,
                    COUNT(*) - COUNT(nort_user_id) AS missing
                FROM {table}
            """)).fetchone()
            total, filled, missing = result
            pct = f"{(filled/total*100):.0f}%" if total > 0 else "n/a"
            flag = "OK " if missing == 0 else "!!!"
            print(f"    {flag}  {table:<28} total={total}  filled={filled}  missing={missing}  ({pct})")
            if missing > 0:
                samples = conn.execute(text(f"""
                    SELECT telegram_user_id FROM {table}
                    WHERE nort_user_id IS NULL LIMIT 3
                """)).fetchall()
                for s in samples:
                    print(f"           unmatched telegram_user_id: {s[0]}")
        except Exception as e:
            print(f"    ERR  {table}: {e}")

print(f"\n{'═'*60}")
print("  Done. Review any !!! rows above — those users need manual matching.")
print(f"{'═'*60}\n")
