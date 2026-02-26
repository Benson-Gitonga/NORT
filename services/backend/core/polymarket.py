# polymarket.py
# Fetches ALL crypto markets from Polymarket, mirroring the full
# Crypto section visible on polymarket.com/crypto.
#
# Covers every timeframe tab:
#   5 Min / 15 Min / Hourly / 4 Hour  → slug-prefix markets (btc-updown-*)
#   Daily / Weekly / Monthly / Yearly → tag_slug-based searches
#   + Pre-Market / FDV / ETF markets  → via crypto-prices tag
#
# Strategy:
#   1. Fetch each timeframe tag independently
#   2. Filter by crypto-related tags to exclude non-crypto results
#   3. Deduplicate by market ID
#   4. Parse into our Market schema (preserving previous_odds correctly)

import httpx
import os
import json
from datetime import datetime, timezone
from typing import List, Dict, Optional

GAMMA_API = os.getenv("POLYMARKET_API_URL", "https://gamma-api.polymarket.com")

# Tags that identify an event as crypto-related
CRYPTO_TAGS = {
    "crypto", "crypto-prices", "bitcoin", "ethereum", "solana",
    "xrp", "hyperliquid", "megaeth", "stablecoins", "etf",
}

# Slug prefixes for automated 5min/15min/hourly markets
CRYPTO_SLUG_PREFIXES = [
    "btc-updown-5m-",
    "btc-updown-15m-",
    "eth-updown-5m-",
    "eth-updown-15m-",
    "sol-updown-5m-",
    "sol-updown-15m-",
    "xrp-updown-5m-",
    "xrp-updown-15m-",
    "btc-updown-1h-",
    "eth-updown-1h-",
    "btc-updown-4h-",
    "eth-updown-4h-",
]

# Timeframe tags matching the Polymarket sidebar exactly
TIMEFRAME_TAGS = ["daily", "weekly", "monthly", "yearly"]

# Coin label mapping for category field
COIN_LABELS = {
    "btc": "BTC", "bitcoin": "BTC",
    "eth": "ETH", "ethereum": "ETH",
    "sol": "SOL", "solana": "SOL",
    "xrp": "XRP",
    "hyperliquid": "HYPE",
    "megaeth": "ETH",
}


def _get_coin_label(text: str) -> str:
    t = text.lower()
    for key, label in COIN_LABELS.items():
        if key in t:
            return label
    return "Crypto"


def _is_crypto_event(event: Dict) -> bool:
    """Returns True if this event belongs to the crypto category."""
    tags = {t["slug"] for t in (event.get("tags") or [])}
    return bool(tags & CRYPTO_TAGS)


def _fetch_events(params: dict) -> List[Dict]:
    """Single API call with error handling. Returns list of events."""
    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.get(f"{GAMMA_API}/events", params=params)
            r.raise_for_status()
            data = r.json()
            if isinstance(data, list):
                return data
            return data.get("events") or data.get("data") or []
    except Exception as e:
        print(f"[Polymarket] Fetch error (params={params}): {e}")
        return []


def fetch_short_term_crypto_markets(limit: int = 300) -> List[Dict]:
    """
    Fetch ALL crypto markets from Polymarket, covering every tab in the
    Crypto section of polymarket.com/crypto.

    Sources (in order):
      1. Slug-prefix markets  → 5min, 15min, hourly, 4-hour automated markets
      2. Timeframe tag pages  → daily, weekly, monthly, yearly (filtered to crypto)
      3. crypto-prices tag    → catches FDV, ETF, and other price markets
    """
    all_markets: List[Dict] = []
    seen_ids: set = set()

    def _add(market_dict: Dict):
        mid = market_dict.get("id")
        if mid and mid not in seen_ids:
            seen_ids.add(mid)
            all_markets.append(market_dict)

    # ── Source 1: Slug-prefix markets (5min / 15min / hourly / 4h) ──────────
    for coin_prefix in ["btc-updown", "eth-updown", "sol-updown", "xrp-updown"]:
        events = _fetch_events({
            "active":  "true",
            "closed":  "false",
            "limit":   50,
            "slug":    coin_prefix,
            "_sort":   "end_date",
            "_order":  "desc",
        })
        for ev in events:
            for m in _extract_markets(ev):
                _add(m)

    # ── Source 2: Timeframe tag pages (daily / weekly / monthly / yearly) ────
    for tag in TIMEFRAME_TAGS:
        events = _fetch_events({
            "active":   "true",
            "closed":   "false",
            "limit":    50,
            "tag_slug": tag,
            "_sort":    "volume24hr",
            "_order":   "desc",
        })
        for ev in events:
            if not _is_crypto_event(ev):
                continue    # skip non-crypto events (stocks, politics, etc.)
            for m in _extract_markets(ev):
                _add(m)

    # ── Source 3: crypto-prices tag (FDV, ETF, price-range markets) ─────────
    events = _fetch_events({
        "active":   "true",
        "closed":   "false",
        "limit":    100,
        "tag_slug": "crypto-prices",
        "_sort":    "volume24hr",
        "_order":   "desc",
    })
    for ev in events:
        for m in _extract_markets(ev):
            _add(m)

    print(f"[Polymarket] Total crypto markets collected: {len(all_markets)}")

    # Sort by volume descending — most active markets first
    all_markets.sort(key=lambda m: m.get("volume", 0), reverse=True)
    return all_markets[:limit]


def _extract_markets(event: Dict) -> List[Dict]:
    """Extract and parse all child markets from a Polymarket event."""
    results = []
    event_title = event.get("title") or ""
    # Pass event-level volume fields down so parse_market can use them
    event_v24  = event.get("volume24hr") or 0
    event_v1wk = event.get("volume1wk") or 0

    for m in (event.get("markets") or []):
        if not m.get("question"):
            m["question"] = event_title
        parsed = parse_market(m, event_title, event_v24, event_v1wk)
        if parsed:
            results.append(parsed)
    return results


def parse_market(
    item: Dict,
    event_title: str = "",
    event_v24: float = 0,
    event_v1wk: float = 0,
) -> Optional[Dict]:
    """
    Converts a raw Polymarket market item into our Market schema dict.

    Key fix vs old version:
      previous_odds is set to None (not current_odds) for brand-new markets.
      The sync_markets() upsert in markets.py will handle preserving the
      real previous_odds on subsequent syncs.
    """
    market_id = str(item.get("id") or item.get("conditionId") or "")
    if not market_id:
        return None

    question = (item.get("question") or event_title or "Unknown").strip()

    # Parse current YES price from outcomePrices[0]
    try:
        prices_raw = item.get("outcomePrices", "[]")
        if isinstance(prices_raw, str):
            prices_raw = json.loads(prices_raw)
        current_odds = float(prices_raw[0]) if prices_raw else 0.5
        # Clamp to valid range — skip obviously invalid markets
        if not (0.0 <= current_odds <= 1.0):
            current_odds = 0.5
    except Exception:
        current_odds = 0.5

    # Parse expiry
    try:
        end_str = item.get("endDate") or item.get("endDateIso") or ""
        if end_str:
            expires_at = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
        else:
            expires_at = datetime(2099, 1, 1)
    except Exception:
        expires_at = datetime(2099, 1, 1)

    # Volume: prefer market-level 24hr, fall back to event-level
    volume24hr = float(item.get("volume24hr") or 0)
    if volume24hr == 0:
        volume24hr = float(event_v24 or 0)

    volume1wk  = float(item.get("volume1wk") or event_v1wk or 0)
    avg_volume = (volume1wk / 7.0) if volume1wk > 0 else max(volume24hr, 1.0)

    return {
        "id":            market_id,
        "question":      question,
        "category":      _get_coin_label(question),
        "current_odds":  current_odds,
        # FIX for issue #7: previous_odds is intentionally None for new markets.
        # On a brand-new insert, markets.py will store 0.5 as default.
        # On second sync, markets.py sets previous_odds = old current_odds correctly.
        "previous_odds": None,
        "volume":        volume24hr,
        "avg_volume":    avg_volume,
        "is_active":     bool(item.get("active", True)),
        "expires_at":    expires_at,
    }
