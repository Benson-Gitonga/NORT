# polymarket.py
# Fetches crypto markets from the Polymarket Gamma API

import httpx
import os
import json
from datetime import datetime, timezone
from typing import List, Dict, Optional

POLYMARKET_API_URL = os.getenv("POLYMARKET_API_URL", "https://gamma-api.polymarket.com")

CRYPTO_KEYWORDS = [
    "bitcoin", "btc", "ethereum", "eth", "solana", "sol",
    "ripple", "xrp", "dogecoin", "doge", "binance", "bnb",
    "avalanche", "avax", "chainlink", "link", "cardano", "ada",
    "polygon", "matic", "crypto", "cryptocurrency", "defi",
    "stablecoin", "usdc", "usdt", "coinbase", "blockchain",
]


def _is_crypto_market(item: Dict) -> bool:
    question = (item.get("question") or "").lower()
    category = (item.get("category") or "").lower()
    slug     = (item.get("slug") or "").lower()
    if "crypto" in category or "bitcoin" in category or "ethereum" in category:
        return True
    combined = question + " " + slug
    return any(kw in combined for kw in CRYPTO_KEYWORDS)


def fetch_short_term_crypto_markets(limit: int = 500) -> List[Dict]:
    """Fetches active markets from Polymarket and returns crypto-related ones."""
    url = f"{POLYMARKET_API_URL}/markets"
    # Fetch a large pool — category is null on all markets so we filter by keyword
    params = {"active": "true", "closed": "false", "limit": limit}

    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            raw_markets = response.json()
    except Exception as e:
        print(f"[Polymarket] Fetch error: {e}")
        return []

    # Handle both list and dict wrapper responses
    if isinstance(raw_markets, dict):
        raw_markets = raw_markets.get("markets") or raw_markets.get("data") or []
    if not isinstance(raw_markets, list):
        print(f"[Polymarket] Unexpected response type: {type(raw_markets)}")
        return []

    crypto_markets = []
    for item in raw_markets:
        try:
            if _is_crypto_market(item):
                parsed = parse_market(item)
                if parsed and parsed["id"]:
                    crypto_markets.append(parsed)
        except Exception as e:
            print(f"[Polymarket] Skipping {item.get('id')}: {e}")

    print(f"[Polymarket] Fetched {len(raw_markets)} total, kept {len(crypto_markets)} crypto markets.")
    return crypto_markets


def parse_market(item: Dict) -> Optional[Dict]:
    """Converts a raw Polymarket API item to our Market schema dict."""
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
