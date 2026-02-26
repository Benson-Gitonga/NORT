# polymarket.py
# Fetches short-term crypto price markets from Polymarket
# Targets: BTC/ETH/SOL 5-min, 15-min, hourly "Up or Down" markets
# These have slugs like: btc-updown-5m-*, btc-updown-15m-*, eth-updown-5m-*
# Plus daily price markets: bitcoin-above-on-*, bitcoin-price-on-*

import httpx
import os
import json
from datetime import datetime, timezone
from typing import List, Dict, Optional

GAMMA_API = os.getenv("POLYMARKET_API_URL", "https://gamma-api.polymarket.com")

# Slug prefixes that identify short-term crypto price markets
# These are the live trading markets on Polymarket
CRYPTO_SLUG_PREFIXES = [
    "btc-updown-5m-",
    "btc-updown-15m-",
    "eth-updown-5m-",
    "eth-updown-15m-",
    "sol-updown-5m-",
    "sol-updown-15m-",
    "xrp-updown-5m-",
    "xrp-updown-15m-",
]

# Question text patterns for daily/weekly price markets
PRICE_MARKET_PATTERNS = [
    "bitcoin up or down",
    "bitcoin above",
    "bitcoin price on",
    "eth up or down",
    "ethereum up or down",
    "solana up or down",
    "xrp up or down",
]

# Coin label mapping
COIN_LABELS = {
    "btc": "BTC", "bitcoin": "BTC",
    "eth": "ETH", "ethereum": "ETH",
    "sol": "SOL", "solana": "SOL",
    "xrp": "XRP",
}


def _get_coin_label(text: str) -> str:
    t = text.lower()
    for key, label in COIN_LABELS.items():
        if key in t:
            return label
    return "Crypto"


def _is_target_market(event: Dict) -> bool:
    """Returns True if this event is a short-term crypto price market."""
    slug     = (event.get("slug") or "").lower()
    title    = (event.get("title") or "").lower()

    # Match slug prefixes (5min/15min automated markets)
    for prefix in CRYPTO_SLUG_PREFIXES:
        if slug.startswith(prefix):
            return True

    # Match question text patterns (daily price markets)
    for pattern in PRICE_MARKET_PATTERNS:
        if pattern in title:
            return True

    return False


def fetch_short_term_crypto_markets(limit: int = 300) -> List[Dict]:
    """
    Fetch short-term crypto price markets from Polymarket.
    Strategy:
      1. Search events with slug pattern for 5min/15min markets
      2. Fetch recent events tagged 'bitcoin' for daily markets
      3. Combine and deduplicate
    """
    all_markets = []
    seen_ids = set()

    # --- Strategy 1: Search for slug-based 5min/15min markets ---
    for coin_prefix in ["btc-updown", "eth-updown", "sol-updown", "xrp-updown"]:
        try:
            with httpx.Client(timeout=15.0) as client:
                r = client.get(f"{GAMMA_API}/events", params={
                    "active":   "true",
                    "closed":   "false",
                    "limit":    50,
                    "slug":     coin_prefix,
                    "_sort":    "end_date",
                    "_order":   "desc",   # newest ending first = most current
                })
                data = r.json()
                if isinstance(data, dict):
                    data = data.get("events") or data.get("data") or []
                if isinstance(data, list):
                    for event in data:
                        for m in _extract_markets(event):
                            if m["id"] not in seen_ids:
                                seen_ids.add(m["id"])
                                all_markets.append(m)
        except Exception as e:
            print(f"[Polymarket] Slug search error for {coin_prefix}: {e}")

    # --- Strategy 2: Fetch events by bitcoin/ethereum/solana tag ---
    for tag in ["bitcoin", "ethereum", "solana", "xrp"]:
        try:
            with httpx.Client(timeout=15.0) as client:
                r = client.get(f"{GAMMA_API}/events", params={
                    "active":   "true",
                    "closed":   "false",
                    "limit":    50,
                    "tag_slug": tag,
                    "_sort":    "end_date",
                    "_order":   "desc",
                })
                data = r.json()
                if isinstance(data, dict):
                    data = data.get("events") or data.get("data") or []
                if isinstance(data, list):
                    for event in data:
                        if not _is_target_market(event):
                            continue
                        for m in _extract_markets(event):
                            if m["id"] not in seen_ids:
                                seen_ids.add(m["id"])
                                all_markets.append(m)
        except Exception as e:
            print(f"[Polymarket] Tag search error for {tag}: {e}")

    # --- Strategy 3: Search API for "bitcoin up or down" ---
    for query in ["bitcoin up or down", "bitcoin above", "bitcoin price on"]:
        try:
            with httpx.Client(timeout=15.0) as client:
                r = client.get(f"{GAMMA_API}/events", params={
                    "active":  "true",
                    "closed":  "false",
                    "limit":   30,
                    "search":  query,
                    "_sort":   "end_date",
                    "_order":  "desc",
                })
                data = r.json()
                if isinstance(data, dict):
                    data = data.get("events") or data.get("data") or []
                if isinstance(data, list):
                    for event in data:
                        for m in _extract_markets(event):
                            if m["id"] not in seen_ids:
                                seen_ids.add(m["id"])
                                all_markets.append(m)
        except Exception as e:
            print(f"[Polymarket] Search error for '{query}': {e}")

    print(f"[Polymarket] Total short-term crypto markets found: {len(all_markets)}")

    # Sort by volume desc — active markets with real trading show first
    all_markets.sort(key=lambda m: m.get("volume", 0), reverse=True)

    return all_markets[:limit]


def _extract_markets(event: Dict) -> List[Dict]:
    """Extract and parse all child markets from an event."""
    results = []
    event_title = event.get("title") or ""
    for m in (event.get("markets") or []):
        if not m.get("question"):
            m["question"] = event_title
        parsed = parse_market(m, event_title)
        if parsed:
            results.append(parsed)
    return results


def parse_market(item: Dict, event_title: str = "") -> Optional[Dict]:
    """Converts a raw Polymarket market item to our Market schema dict."""
    market_id = str(item.get("id") or item.get("conditionId") or "")
    if not market_id:
        return None

    question = item.get("question") or event_title or "Unknown"

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
        "question":      question,
        "category":      _get_coin_label(question),
        "current_odds":  current_odds,
        "previous_odds": current_odds,
        "volume":        volume24hr,
        "avg_volume":    avg_volume,
        "is_active":     bool(item.get("active", True)),
        "expires_at":    expires_at,
    }
