"""
migrate_nort_user_id_fix.py — Fix the two remaining !!! issues from migrate_nort_user_id.py

ISSUE 1 — wallet_config: tg_ prefix mismatch
  wallet_config.telegram_user_id = 'tg_7725363948'
  user.telegram_id               = '7725363948'   (prefix was stripped in Step 1)
  Fix: join on SUBSTRING(telegram_user_id FROM 4) for tg_ rows.

ISSUE 2 — paper_trades: dev_user rows
  These are test records with telegram_user_id = 'dev_user'.
  No real User row exists. Two options — we DELETE them (safe, they are dev data)
  OR create a dev_user sentinel. We delete them here (set DEL_DEV_TRADES = False to skip).

ISSUE 3 — wallet_config: ghost 0x... configs with no User row
  wallet_config rows with a wallet address that never completed registration.
  We log them and leave them — they will link naturally if the user ever registers.
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

DEL_DEV_TRADES = True  # Set False if you want to keep dev_user paper_trades


FIXES = []

# ── FIX 1: wallet_config tg_ prefix mismatch ─────────────────────────────────
# telegram_user_id = 'tg_7725363948' but user.telegram_id = '7725363948'
# Join on the stripped version.
FIXES.append((
    "wallet_config: fix tg_ prefix mismatch (path A retry)",
    """
    UPDATE wallet_config wc
    SET nort_user_id = u.id
    FROM "user" u
    WHERE wc.telegram_user_id LIKE 'tg_%'
      AND u.telegram_id = SUBSTRING(wc.telegram_user_id FROM 4)
      AND wc.nort_user_id IS NULL
    """
))

# Also try path B (via telegram_profile) for the same tg_ rows
FIXES.append((
    "wallet_config: fix tg_ prefix mismatch (path B retry via telegram_profile)",
    """
    UPDATE wallet_config wc
    SET nort_user_id = tp.user_id
    FROM telegram_profile tp
    WHERE wc.telegram_user_id LIKE 'tg_%'
      AND tp.telegram_id = SUBSTRING(wc.telegram_user_id FROM 4)
      AND tp.user_id IS NOT NULL
      AND wc.nort_user_id IS NULL
    """
))

# ── FIX 2: paper_trades dev_user cleanup ─────────────────────────────────────
if DEL_DEV_TRADES:
    FIXES.append((
        "paper_trades: delete dev_user test records",
        "DELETE FROM paper_trades WHERE telegram_user_id = 'dev_user'"
    ))
else:
    FIXES.append((
        "paper_trades: skip dev_user deletion (DEL_DEV_TRADES=False)",
        "SELECT 1"  # no-op
    ))


# ── RUNNER ────────────────────────────────────────────────────────────────────
print("\n── Running targeted fixes...\n")
with engine.connect() as conn:
    for description, sql in FIXES:
        try:
            result = conn.execute(text(sql))
            conn.commit()
            affected = result.rowcount if result.rowcount >= 0 else "?"
            print(f"  OK  {description}  ({affected} rows affected)")
        except Exception as e:
            print(f"  ERR {description}\n      {e}")
            conn.rollback()

# ── FINAL VERIFICATION ────────────────────────────────────────────────────────
print("\n── Final coverage check:\n")

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

with engine.connect() as conn:
    for table in TABLES:
        try:
            row = conn.execute(text(f"""
                SELECT COUNT(*) AS total,
                       COUNT(nort_user_id) AS filled,
                       COUNT(*) - COUNT(nort_user_id) AS missing
                FROM {table}
            """)).fetchone()
            total, filled, missing = row
            if total == 0:
                print(f"  --  {table:<28} (empty)")
                continue
            pct = f"{(filled/total*100):.0f}%"
            flag = "OK " if missing == 0 else "!!!"
            print(f"  {flag}  {table:<28} total={total}  filled={filled}  missing={missing}  ({pct})")
            if missing > 0:
                samples = conn.execute(text(f"""
                    SELECT telegram_user_id FROM {table}
                    WHERE nort_user_id IS NULL LIMIT 5
                """)).fetchall()
                for s in samples:
                    print(f"         unmatched: {s[0]}")
        except Exception as e:
            print(f"  ERR  {table}: {e}")

print("\nDone.\n")
