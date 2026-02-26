# polymarket.py
# Fetches crypto markets from Polymarket using the Events API with tag filtering
# Events API supports tag_slug param which is the correct way to filter by category

import httpx
import os
import json
from datetime import datetime
from typing import List, Dict, Optional

GAMMA_API = os.getenv("POLYMARKET_API_URL", "https://gamma-api.polymarket.com")

# Fallback keyword filter (used only if Events API returns nothing)
CRYPTO_KEYWORDS = [
    "bitcoin", " btc ", "btc $", "btc price", "btc hit", "btc above", "btc below", "btc reach",
    "ethereum", " eth ", "eth $", "eth price", "eth hit", "eth above", "eth below",
    "solana", " sol ", "sol price", "sol hit",
    "ripple", " xrp ", "xrp price",
    "dogecoin", "doge price", "doge hit",
    " bnb ", "bnb price",
    " avax ", "avax price",
    " ada ", "ada price",
    " matic ", "matic price",
    "cryptocurrency", "crypto market", "crypto price",
    "coinbase stock", "binance exchange",
]


def _is_crypto_market(item: Dict) -> bool:
    """Keyword fallback — used when Events API tag filter doesn't work."""
    question = (item.get("question") or "").lower()
    padded = f" {question} "
    return any(kw in padded for kw in CRYPTO_KEYWORDS)


def _fetch_events_by_tag(tag_slug: str, limit: int = 100) -> List[Dict]:
    """
    Fetch events (market groups) from Polymarket filtered by tag slug.
    Each event contains one or more markets.
    """
    url = f"{GAMMA_API}/events"
    all_events = []
    offset = 0

    while len(all_events) < limit:
        params = {
            "active":    "true",
            "closed":    "false",
            "limit":     50,
            "offset":    offset,
            "tag_slug":  tag_slug,
        }
        try:
            with httpx.Client(timeout=15.0) as client:
                r = client.get(url, params=params)
                r.raise_for_status()
                data = r.json()
        except Exception as e:
            print(f"[Polymarket] Events fetch error at offset {offset}: {e}")
            break

        # Events API may return list or dict wrapper
        if isinstance(data, dict):
            data = data.get("events") or data.get("data") or []
        if not isinstance(data, list) or len(data) == 0:
            break

        all_events.extend(data)
        if len(data) < 50:
            break
        offset += 50

    return all_events


def _markets_from_events(events: List[Dict]) -> List[Dict]:
    """Extract and parse all markets from a list of events."""
    markets = []
    for event in events:
        # Each event has a "markets" array
        event_markets = event.get("markets") or []
        for m in event_markets:
            parsed = parse_market(m)
            if parsed and parsed["id"]:
                markets.append(parsed)
    return markets


def fetch_short_term_crypto_markets(limit: int = 200) -> List[Dict]:
    """
    Primary strategy: use Events API with tag_slug=crypto.
    Fallback: paginate Markets API and filter by keyword.
    """
    # Strategy 1: Events API with crypto tag
    print("[Polymarket] Trying Events API with tag_slug=crypto...")
    events = _fetch_events_by_tag("crypto", limit=limit)

    if events:
        markets = _markets_from_events(events)
        print(f"[Polymarket] Got {len(events)} events → {len(markets)} markets via Events API.")
        if markets:
            return markets

    # Strategy 2: Events API with cryptocurrency tag
    print("[Polymarket] Trying tag_slug=cryptocurrency...")
    events = _fetch_events_by_tag("cryptocurrency", limit=limit)
    if events:
        markets = _markets_from_events(events)
        print(f"[Polymarket] Got {len(events)} events → {len(markets)} markets.")
        if markets:
            return markets

    # Strategy 3: Fallback — paginate Markets API, filter by keyword
    print("[Polymarket] Falling back to keyword filter on Markets API...")
    all_raw = []
    for offset in range(0, min(limit, 500), 50):
        try:
            with httpx.Client(timeout=15.0) as client:
                r = client.get(f"{GAMMA_API}/markets", params={
                    "active": "true", "closed": "false", "limit": 50, "offset": offset
                })
                page = r.json()
                if isinstance(page, dict):
                    page = page.get("markets") or page.get("data") or []
                if not isinstance(page, list) or len(page) == 0:
                    break
                all_raw.extend(page)
                if len(page) < 50:
                    break
        except Exception as e:
            print(f"[Polymarket] Markets page error at {offset}: {e}")
            break

    crypto = []
    for item in all_raw:
        if _is_crypto_market(item):
            parsed = parse_market(item)
            if parsed and parsed["id"]:
                crypto.append(parsed)

    print(f"[Polymarket] Keyword fallback: {len(all_raw)} scanned → {len(crypto)} crypto markets.")
    return crypto


def parse_market(item: Dict) -> Optional[Dict]:
    """Converts a raw Polymarket market item to our Market schema dict."""
    market_id = item.get("id") or item.get("conditionId") or ""
    if not market_id:
        return None

    try:
        outcomes = item.get("outcomePrices", "[]")
        if isinstance(outcomes, str):
            outcomes = json.loads(outcomes)
        current_odds = float(outcomes[0]) if outcomes else 0.5
    except Exception:
        current_odds = 0.5

    try:
        end_str = item.get("endDate") or ""
        expires_at = datetime.fromisoformat(end_str.replace("Z", "+00:00")) if end_str else datetime(2099, 1, 1)
    except Exception:
        expires_at = datetime(2099, 1, 1)

    volume24hr = float(item.get("volume24hr") or item.get("volume") or 0)
    volume1wk  = float(item.get("volume1wk") or 0)
    avg_volume = (volume1wk / 7) if volume1wk > 0 else max(volume24hr, 1.0)

    return {
        "id":            market_id,
        "question":      item.get("question") or "Unknown",
        "category":      item.get("category") or "crypto",
        "current_odds":  current_odds,
        "previous_odds": current_odds,
        "volume":        volume24hr,
        "avg_volume":    avg_volume,
        "is_active":     bool(item.get("active", True)),
        "expires_at":    expires_at,
    }
