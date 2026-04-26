"""
debug_db.py — Run this to diagnose DB issues instantly.
Usage: python debug_db.py

Checks:
  1. What DATABASE_URL is being used (Neon or SQLite?)
  2. Can we connect at all?
  3. Which tables exist in the DB right now?
  4. Which tables are MISSING (defined in models but not in DB)?
  5. Row counts for key tables
  6. Last 5 audit_log entries (advice usage tracking)
  7. Force re-runs init_db() to create missing tables
"""
import os, sys
from dotenv import load_dotenv
load_dotenv(override=True)

# ── 1. Show which DB we're hitting ───────────────────────────
raw_url = os.getenv("DATABASE_URL", "")
if raw_url:
    safe = raw_url[:40] + "..." if len(raw_url) > 40 else raw_url
    print(f"\n✅ DATABASE_URL found: {safe}")
    print(f"   Type: {'Neon/PostgreSQL' if 'neon' in raw_url or 'postgres' in raw_url else 'Other'}")
else:
    print("\n⚠️  DATABASE_URL not set — falling back to SQLite")
    print("   This means data is NOT going to Neon!")

# ── 2. Connect and list existing tables ──────────────────────
from sqlalchemy import create_engine, text, inspect

def build_url():
    url = os.getenv("DATABASE_URL", "").strip()
    if url:
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        for junk in ["&channel_binding=require", "channel_binding=require&", "?channel_binding=require"]:
            url = url.replace(junk, "")
        return url
    base = os.path.dirname(os.path.abspath(__file__))
    return f"sqlite:///{os.path.join(base, 'data', 'assistant.db')}"

url = build_url()
is_sqlite = url.startswith("sqlite")

try:
    engine = create_engine(url, echo=False)
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    print("✅ DB connection successful\n")
except Exception as e:
    print(f"❌ DB connection FAILED: {e}")
    sys.exit(1)

# ── 3. Tables that exist right now ───────────────────────────
inspector = inspect(engine)
existing  = set(inspector.get_table_names())
print(f"📋 Tables currently in DB ({len(existing)}):")
for t in sorted(existing):
    print(f"   ✅ {t}")

# ── 4. Tables that SHOULD exist (from models.py) ─────────────
expected = {
    "user", "market", "aisignal", "payment", "telegram_profile",
    "trade", "paper_trades", "wallet_config", "leaderboard_snapshots",
    "conversations", "user_permissions", "audit_logs",
    "pending_trades", "alert_history", "bridge_transactions", "real_trades",
}
missing = expected - existing
if missing:
    print(f"\n❌ MISSING tables ({len(missing)}) — these were never created:")
    for t in sorted(missing):
        print(f"   ❌ {t}")
    print("\n   → Running init_db() now to create them...")
    from services.backend.data.database import init_db
    init_db()
    # Re-check
    existing2 = set(inspect(engine).get_table_names())
    still_missing = expected - existing2
    if still_missing:
        print(f"\n   ❌ Still missing after init_db(): {still_missing}")
    else:
        print("   ✅ All tables created successfully!")
else:
    print("\n✅ All expected tables exist")

# ── 5. Row counts ─────────────────────────────────────────────
print("\n📊 Row counts:")
key_tables = [
    "user", "market", "paper_trades", "wallet_config",
    "audit_logs", "user_permissions", "conversations",
    "pending_trades", "leaderboard_snapshots",
]
with engine.connect() as conn:
    for t in key_tables:
        if t in existing:
            try:
                count = conn.execute(text(f'SELECT COUNT(*) FROM "{t}"')).scalar()
                flag = "⚠️ " if count == 0 else "   "
                print(f"{flag} {t}: {count} rows")
            except Exception as e:
                print(f"   ⚠️  {t}: error — {e}")
        else:
            print(f"   ❌ {t}: table does not exist")

# ── 6. Last 5 audit_log entries (advice usage) ───────────────
print("\n🔍 Last 5 audit_log entries (advice calls):")
if "audit_logs" in existing:
    with engine.connect() as conn:
        try:
            rows = conn.execute(text(
                'SELECT telegram_user_id, action, premium, success, created_at '
                'FROM audit_logs ORDER BY created_at DESC LIMIT 5'
            )).fetchall()
            if rows:
                for r in rows:
                    print(f"   user={str(r[0])[:20]:20} action={r[1]:10} premium={r[2]} success={r[3]} at={str(r[4])[:19]}")
            else:
                print("   ⚠️  audit_logs is empty — advice calls are not being recorded")
                print("      → Check that the backend is using Neon (not SQLite) and restarted after the DB fix")
        except Exception as e:
            print(f"   ❌ Error querying audit_logs: {e}")
else:
    print("   ❌ audit_logs table does not exist yet")

# ── 7. Last 5 user_permissions ───────────────────────────────
print("\n🔍 Last 5 user_permissions rows:")
if "user_permissions" in existing:
    with engine.connect() as conn:
        try:
            rows = conn.execute(text(
                'SELECT telegram_user_id, auto_trade_enabled, trade_mode, max_bet_size, min_confidence '
                'FROM user_permissions ORDER BY updated_at DESC LIMIT 5'
            )).fetchall()
            if rows:
                for r in rows:
                    print(f"   user={str(r[0])[:30]:30} auto={r[1]} mode={r[2]} max=${r[3]} conf={r[4]}")
            else:
                print("   ⚠️  user_permissions is empty")
        except Exception as e:
            print(f"   ❌ Error: {e}")
else:
    print("   ❌ user_permissions table does not exist")

# ── 8. Check .env is loaded ───────────────────────────────────
print("\n🔑 Key env vars:")
for key in ["DATABASE_URL", "OPENROUTER_API_KEY", "TAVILY_API_KEY", "OPENROUTER_API_KEY_FALLBACK"]:
    val = os.getenv(key, "")
    if val:
        print(f"   ✅ {key}: set ({len(val)} chars)")
    else:
        print(f"   ❌ {key}: NOT SET")

print("\n" + "="*50)
print("  Done. Paste the output above to diagnose issues.")
print("="*50 + "\n")
