"""
test_all.py — NORT Full API Test Suite
Run with: python test_all.py
Make sure the server is running: uvicorn services.backend.main:app --reload --port 8000
"""

import requests
import json
import time

BASE = "http://localhost:8000"

TEST_WALLET   = "0x690145312876Cf3423f2aCF3f5d8eEDcfD081948"
TEST_TELEGRAM = "test_user_001"
TEST_MARKET   = None   # auto-discovered from /markets

PASS = "✅"
FAIL = "❌"

results = []

def test(name, fn):
    try:
        result = fn()
        status = PASS if result else FAIL
        results.append((status, name))
        print(f"{status} {name}")
        return result
    except Exception as e:
        results.append((FAIL, name))
        print(f"{FAIL} {name} — {e}")
        return None

def post(path, body):
    return requests.post(f"{BASE}{path}", json=body, timeout=120)

def get(path):
    return requests.get(f"{BASE}{path}", timeout=30)

print("\n" + "="*60)
print("  NORT API TEST SUITE")
print("="*60 + "\n")

# ── 1. HEALTH ────────────────────────────────────────────────
print("\n── 1. HEALTH ──────────────────────────────────────────────")

def t_health():
    r = get("/")
    assert r.status_code == 200 and r.json().get("status") == "online"
    return True

test("GET / — server online", t_health)

# ── 2. MARKETS & SIGNALS ─────────────────────────────────────
print("\n── 2. MARKETS & SIGNALS ───────────────────────────────────")

def t_markets():
    r = get("/markets/?limit=5")
    assert r.status_code == 200, f"Got {r.status_code}: {r.text[:200]}"
    data = r.json()
    # Response is {"markets": [...], "count": N, "cached_at": "..."}
    market_list = data.get("markets") or data if isinstance(data, list) else []
    assert len(market_list) > 0, f"No markets returned. Keys: {list(data.keys())}"
    global TEST_MARKET
    TEST_MARKET = market_list[0]["id"]
    print(f"   → {data.get('count','?')} markets | Using: {TEST_MARKET}")
    print(f"   → Question: {market_list[0].get('question','')[:60]}...")
    return True

def t_signals():
    r = get("/signals/?top=5&category=crypto")
    assert r.status_code == 200
    data = r.json()
    items = data if isinstance(data, list) else data.get("signals", [])
    print(f"   → Got {len(items)} signals")
    return True

test("GET /markets/?limit=5", t_markets)
test("GET /signals/?top=5&category=crypto", t_signals)

# ── 3. WALLET ────────────────────────────────────────────────
print("\n── 3. WALLET ──────────────────────────────────────────────")

def t_wallet_connect():
    r = post("/api/wallet/connect", {"wallet_address": TEST_WALLET})
    assert r.status_code == 200, f"Got {r.status_code}: {r.text[:100]}"
    return True

def t_wallet_summary():
    r = get(f"/api/wallet/summary?wallet_address={TEST_WALLET}")
    assert r.status_code == 200
    data = r.json()
    print(f"   → Paper balance: ${data.get('paper_balance', data.get('balance','?'))}")
    return True

def t_wallet_mode():
    r = get(f"/api/wallet/mode?wallet_address={TEST_WALLET}")
    assert r.status_code == 200
    return True

test("POST /api/wallet/connect", t_wallet_connect)
test("GET  /api/wallet/summary", t_wallet_summary)
test("GET  /api/wallet/mode", t_wallet_mode)

# ── 4. PERMISSIONS ───────────────────────────────────────────
print("\n── 4. PERMISSIONS ─────────────────────────────────────────")

def t_perm_create():
    r = post("/api/permissions", {
        "telegram_user_id": TEST_TELEGRAM,
        "auto_trade_enabled": False,
        "max_bet_size": 10.0,
        "min_confidence": 0.75,
        "trade_mode": "paper",
        "preferred_language": "en"
    })
    assert r.status_code == 200, f"Got {r.status_code}: {r.text[:200]}"
    data = r.json()
    assert data.get("telegram_user_id") == TEST_TELEGRAM
    return True

def t_perm_read():
    r = get(f"/api/permissions/{TEST_TELEGRAM}")
    assert r.status_code == 200, f"Got {r.status_code}: {r.text[:200]}"
    data = r.json()
    print(f"   → auto_trade={data.get('auto_trade_enabled')} mode={data.get('trade_mode')} max_bet=${data.get('max_bet_size')}")
    return True

def t_perm_invalid_mode():
    r = post("/api/permissions", {
        "telegram_user_id": TEST_TELEGRAM,
        "trade_mode": "invalid_mode"
    })
    assert r.status_code == 400, f"Expected 400, got {r.status_code}: {r.text[:100]}"
    print(f"   → Correctly rejected: {r.json().get('detail','')[:60]}")
    return True

test("POST /api/permissions (create/upsert)", t_perm_create)
test("GET  /api/permissions/{id}", t_perm_read)
test("POST /api/permissions (invalid trade_mode → 400)", t_perm_invalid_mode)

# ── 5. FREE ADVICE (anonymous) ───────────────────────────────
print("\n── 5. FREE ADVICE (anonymous) ─────────────────────────────")

def t_free_advice_anon():
    assert TEST_MARKET, "TEST_MARKET not set — fix the /markets test first"
    r = post("/agent/advice", {"market_id": TEST_MARKET, "premium": False})
    assert r.status_code == 200, f"Got {r.status_code}: {r.text[:300]}"
    data = r.json()
    assert data.get("summary"), f"Empty summary. Full response: {data}"
    assert data.get("suggested_plan") in ("BUY YES", "BUY NO", "WAIT"), f"Bad plan: {data.get('suggested_plan')}"
    assert 0.0 <= float(data.get("confidence", -1)) <= 1.0
    print(f"   → Plan: {data['suggested_plan']} | Confidence: {int(data['confidence']*100)}%")
    print(f"   → {data['summary'][:80]}...")
    return True

test("POST /agent/advice (free, no telegram_id)", t_free_advice_anon)

# ── 6. FREE ADVICE + CACHE ───────────────────────────────────
print("\n── 6. FREE ADVICE (telegram_id + cache) ───────────────────")

def t_free_advice_with_id():
    r = post("/agent/advice", {
        "market_id": TEST_MARKET,
        "telegram_id": TEST_TELEGRAM,
        "premium": False
    })
    assert r.status_code == 200, f"Got {r.status_code}: {r.text[:300]}"
    data = r.json()
    print(f"   → Plan: {data.get('suggested_plan')} | Confidence: {int(data.get('confidence',0)*100)}%")
    return True

def t_advice_cache():
    start = time.time()
    r = post("/agent/advice", {
        "market_id": TEST_MARKET,
        "telegram_id": TEST_TELEGRAM,
        "premium": False
    })
    elapsed = time.time() - start
    assert r.status_code == 200
    data = r.json()
    cached = data.get("stale_data_warning")
    print(f"   → Elapsed: {elapsed:.1f}s | Cache hit: {'YES — ' + cached[:50] if cached else 'NO (first call cached now)'}")
    return True

test("POST /agent/advice (free, with telegram_id)", t_free_advice_with_id)
test("POST /agent/advice (2nd call — expect cache hit)", t_advice_cache)

# ── 7. SWAHILI ───────────────────────────────────────────────
print("\n── 7. SWAHILI ADVICE ──────────────────────────────────────")

def t_swahili():
    r = post("/agent/advice", {
        "market_id": TEST_MARKET,
        "telegram_id": TEST_TELEGRAM + "_sw",
        "premium": False,
        "language": "sw"
    })
    assert r.status_code == 200, f"Got {r.status_code}: {r.text[:300]}"
    data = r.json()
    plan = data.get("suggested_plan", "")
    valid = {"NUNUA NDIYO", "NUNUA HAPANA", "SUBIRI", "BUY YES", "BUY NO", "WAIT"}
    assert plan in valid, f"Unexpected plan: {plan}"
    print(f"   → Swahili plan: {plan} | Summary snippet: {data.get('summary','')[:60]}...")
    return True

test("POST /agent/advice (language=sw)", t_swahili)

# ── 8. DAILY LIMIT ───────────────────────────────────────────
print("\n── 8. DAILY LIMIT ─────────────────────────────────────────")
print("   ⚠️  Skipped (burns ~3 min + API credits). Uncomment to run:")
print("   # test('Daily limit → 429 on 6th call', t_daily_limit)")

# ── 9. PREMIUM (no payment → 402) ───────────────────────────
print("\n── 9. PREMIUM ADVICE ──────────────────────────────────────")

def t_premium_gate():
    r = post("/agent/advice", {
        "market_id": TEST_MARKET,
        "telegram_id": TEST_TELEGRAM,
        "premium": True
    })
    print(f"   → Status: {r.status_code}")
    assert r.status_code in (402, 200), f"Unexpected {r.status_code}: {r.text[:100]}"
    if r.status_code == 402:
        print("   → x402 gate working: 402 Payment Required ✅")
    else:
        print("   → User already has premium access in DB (200 OK)")
    return True

test("POST /agent/advice (premium=True → 402 or 200)", t_premium_gate)

# ── 12. PAPER TRADING ────────────────────────────────────────
print("\n── 12. PAPER TRADING ──────────────────────────────────────")

trade_id = None

def t_paper_buy():
    global trade_id
    assert TEST_MARKET, "Need TEST_MARKET"
    r = post("/papertrade", {
        "telegram_user_id": TEST_TELEGRAM,
        "market_id": TEST_MARKET,
        "market_question": "Test market question",
        "outcome": "YES",
        "shares": 10.0,
        "price_per_share": 0.55,
        "direction": "BUY"
    })
    assert r.status_code == 200, f"Got {r.status_code}: {r.text[:200]}"
    data = r.json()
    trade_id = data.get("id") or data.get("trade_id")
    print(f"   → Trade ID: {trade_id} | Cost: ${data.get('total_cost','?')}")
    return True

def t_trade_value():
    if not trade_id:
        print("   → Skipped (buy failed)")
        return True
    r = get(f"/api/trade/value/{trade_id}")
    assert r.status_code == 200, f"Got {r.status_code}: {r.text[:100]}"
    data = r.json()
    print(f"   → Value: ${data.get('value', data.get('current_value','?'))}")
    return True

def t_trade_sell():
    if not trade_id:
        print("   → Skipped (buy failed)")
        return True
    r = post(f"/api/trade/sell/{trade_id}", {})
    assert r.status_code == 200, f"Got {r.status_code}: {r.text[:100]}"
    print(f"   → {str(r.json())[:80]}")
    return True

test("POST /papertrade (buy YES)", t_paper_buy)
test("GET  /api/trade/value/{id}", t_trade_value)
test("POST /api/trade/sell/{id}", t_trade_sell)

# ── 13. AUTO-TRADE ───────────────────────────────────────────
print("\n── 13. AUTO-TRADE ─────────────────────────────────────────")

def t_autotrade_enable():
    r = post("/api/permissions", {
        "telegram_user_id": TEST_TELEGRAM,
        "auto_trade_enabled": True,
        "trade_mode": "confirm",
        "max_bet_size": 5.0,
        "min_confidence": 0.50
    })
    assert r.status_code == 200, f"Got {r.status_code}: {r.text[:200]}"
    data = r.json()
    assert data.get("auto_trade_enabled") is True, f"Key missing: {data}"
    print(f"   → Enabled | mode=confirm | max_bet=$5 | min_conf=0.50")
    return True

def t_autotrade_trigger():
    assert TEST_MARKET, "Need TEST_MARKET"
    r = post("/agent/advice", {
        "market_id": TEST_MARKET,
        "telegram_id": TEST_TELEGRAM,
        "premium": False
    })
    assert r.status_code == 200, f"Got {r.status_code}: {r.text[:300]}"
    data = r.json()
    auto = data.get("auto_trade_result")
    if auto:
        print(f"   → executed={auto.get('executed')} mode={auto.get('mode')}")
        print(f"   → {auto.get('reason','')[:80]}")
    else:
        print("   → auto_trade_result absent")
    return True

def t_autotrade_disable():
    r = post("/api/permissions", {
        "telegram_user_id": TEST_TELEGRAM,
        "auto_trade_enabled": False
    })
    assert r.status_code == 200, f"Got {r.status_code}: {r.text[:200]}"
    assert r.json().get("auto_trade_enabled") is False
    print("   → Disabled ✅")
    return True

test("POST /permissions (enable confirm mode)", t_autotrade_enable)
test("POST /agent/advice (auto_trade_result)", t_autotrade_trigger)
test("POST /permissions (disable)", t_autotrade_disable)

# -- 14. LEADERBOARD ---
print("\n-- 14. LEADERBOARD ---")

def t_leaderboard():
    r = get("/leaderboard")
    assert r.status_code == 200
    data = r.json()
    count = len(data) if isinstance(data, list) else data.get("count", "?")
    print(f"   -> {count} entries")
    return True

test("GET /leaderboard", t_leaderboard)

# -- SUMMARY ---
print("\n" + "="*60)
passed = sum(1 for s, _ in results if s == PASS)
failed = sum(1 for s, _ in results if s == FAIL)
for status, name in results:
    print(f"  {status} {name}")
print(f"\n  {passed}/{len(results)} passed")
if TEST_MARKET:
    print(f"  Swagger: http://localhost:8000/docs")
print("="*60)
