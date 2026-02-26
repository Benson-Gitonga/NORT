# polymarket.py
# Fetches SHORT-TERM CRYPTO markets only from the Polymarket Gamma API
# Filters for: 5-minute, 15-minute, and hourly crypto price markets

import httpx
import os
import json
import re
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional

POLYMARKET_API_URL = os.getenv("POLYMARKET_API_URL", "https://gamma-api.polymarket.com")

# ─────────────────────────────────────────────
# FILTERS — what counts as a short-term crypto market
# ─────────────────────────────────────────────

# Keywords that identify short-term crypto markets by question text
SHORT_TERM_KEYWORDS = [
    "5 minutes", "5-minute", "5min",
    "15 minutes", "15-minute", "15min",
    "1 hour", "1-hour", "hourly", "60 minutes",
    "next hour", "this hour",
    "in the next 5", "in the next 15",
]

# Crypto tokens we care about
CRYPTO_KEYWORDS = [
    "btc", "bitcoin",
    "eth", "ethereum",
    "sol", "solana",
    "bnb", "binance",
    "xrp", "ripple",
    "doge", "dogecoin",
    "avax", "avalanche",
    "matic", "polygon",
    "link", "chainlink",
    "ada", "cardano",
]

# Maximum market duration in hours — anything longer is NOT short-term
MAX_DURATION_HOURS = 2


def _is_short_term_crypto(item: Dict) -> bool:
    """
    Returns True if this market is a short-term (5min/15min/1hr) crypto price market.
    Checks: question text, tags, category, and market duration.
    """
    question = (item.get("question") or "").lower()
    category = (item.get("category") or "").lower()
    tags = [t.lower() for t in (item.get("tags") or [])]
    slug = (item.get("slug") or "").lower()

    # Must mention a crypto token
    has_crypto = any(kw in question or kw in slug for kw in CRYPTO_KEYWORDS)
    if not has_crypto:
        return False

    # Must mention a short-term timeframe in the question OR be in crypto category
    # with a very short expiry window
    has_timeframe_keyword = any(kw in question for kw in SHORT_TERM_KEYWORDS)

    # Check duration from endDate — must expire within MAX_DURATION_HOURS
    short_duration = False
    try:
        end_date_str = item.get("endDate") or item.get("end_date_iso") or ""
        if end_date_str:
            end_date = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            duration_hours = (end_date - now).total_seconds() / 3600
            # Accept markets that expire within 2 hours (they're already running)
            # OR were created as short-term (duration from creation < 2 hours)
            if 0 < duration_hours <= MAX_DURATION_HOURS:
                short_duration = True
    except Exception:
        pass

    return has_timeframe_keyword or (has_crypto and short_duration)


# ─────────────────────────────────────────────
# FETCH — pull markets from Polymarket API
# ─────────────────────────────────────────────

def fetch_short_term_crypto_markets(limit: int = 200) -> List[Dict]:
    """
    Fetches active markets from Polymarket and filters to
    short-term crypto markets only (5min / 15min / 1hr).

    Returns a list of parsed market dicts ready to upsert into the DB.
    """
    url = f"{POLYMARKET_API_URL}/markets"
    params = {
        "active": "true",
        "closed": "false",
        "limit": limit,
        "tag_slug": "crypto",       # pre-filter by crypto tag on the API side
    }

    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            raw_markets = response.json()
    except Exception as e:
        print(f"[Polymarket] Fetch error: {e}")
        return []

    markets = []
    for item in raw_markets:
        try:
            if not _is_short_term_crypto(item):
                continue
            parsed = parse_market(item)
            if parsed and parsed["id"]:
                markets.append(parsed)
        except Exception as e:
            print(f"[Polymarket] Skipping {item.get('id')}: {e}")
            continue

    print(f"[Polymarket] Fetched {len(raw_markets)} markets, kept {len(markets)} short-term crypto.")
    return markets


# ─────────────────────────────────────────────
# PARSE — convert raw API item to our schema
# ─────────────────────────────────────────────

def parse_market(item: Dict) -> Optional[Dict]:
    """
    Converts a raw Polymarket API response item into a clean
    dict matching the Market table schema.
    """
    try:
        outcomes = item.get("outcomePrices", "[]")
        if isinstance(outcomes, str):
            outcomes = json.loads(outcomes)
        current_odds = float(outcomes[0]) if outcomes else 0.5
    except Exception:
        current_odds = 0.5

    try:
        expires_at = datetime.fromisoformat(
            item.get("endDate", "").replace("Z", "+00:00")
        )
    except Exception:
        expires_at = datetime(2099, 1, 1)

    volume24hr = float(item.get("volume24hr") or 0)
    volume1wk  = float(item.get("volume1wk") or 0)
    avg_volume = (volume1wk / 7) if volume1wk > 0 else volume24hr
    if avg_volume == 0:
        avg_volume = 1.0

    return {
        "id":            item.get("id", ""),
        "question":      item.get("question", "Unknown"),
        "category":      item.get("category", "crypto"),
        "current_odds":  current_odds,
        "previous_odds": current_odds,
        "volume":        volume24hr,
        "avg_volume":    avg_volume,
        "is_active":     item.get("active", True),
        "expires_at":    expires_at,
    }
