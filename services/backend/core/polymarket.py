# polymarket.py
# Fetches crypto markets from the Polymarket Gamma API
# Uses pagination to get enough markets since API caps at 50 per request

import httpx
import os
import json
from datetime import datetime
from typing import List, Dict, Optional

POLYMARKET_API_URL = os.getenv("POLYMARKET_API_URL", "https://gamma-api.polymarket.com")

# Strict crypto keywords — must clearly refer to crypto assets
# Avoid short words like "coin", "link", "sol" that match non-crypto text
CRYPTO_KEYWORDS = [
    "bitcoin", " btc ",  "btc $", "btc price", "btc hit", "btc above", "btc below", "btc reach",
    "ethereum", " eth ", "eth $", "eth price", "eth hit", "eth above", "eth below",
    "solana", " sol ", "sol price", "sol hit",
    "ripple", " xrp ", "xrp price",
    "dogecoin", "doge price", "doge hit",
    " bnb ", "bnb price",
    "avalanche avax", " avax ",
    "chainlink link price",
    "cardano", " ada ",
    "polygon matic", " matic ",
    "cryptocurrency", "crypto market", "crypto price",
    "altcoin", "defi protocol",
    "stablecoin", "usdc depeg", "usdt depeg",
    "coinbase stock", "coinbase ipo",
    "binance exchange",
]

def _is_crypto_market(item: Dict) -> bool:
    """Returns True only if this market is clearly about crypto."""
    question = (item.get("question") or "").lower()
    # Pad with spaces for whole-word matching
    padded = f" {question} "
    return any(kw in padded for kw in CRYPTO_KEYWORDS)


def fetch_short_term_crypto_markets(limit: int = 500) -> List[Dict]:
    """
    Fetches crypto markets from Polymarket using pagination.
    Polymarket API caps at ~50 per request so we paginate with offset.
    """
    url = f"{POLYMARKET_API_URL}/markets"
    all_markets = []
    offset = 0
    page_size = 50  # API max per request

    while len(all_markets) < limit:
        params = {
            "active":  "true",
            "closed":  "false",
            "limit":   page_size,
            "offset":  offset,
        }
        try:
            with httpx.Client(timeout=15.0) as client:
                response = client.get(url, params=params)
                response.raise_for_status()
                page = response.json()
        except Exception as e:
            print(f"[Polymarket] Fetch error at offset {offset}: {e}")
            break

        if isinstance(page, dict):
            page = page.get("markets") or page.get("data") or []
        if not isinstance(page, list) or len(page) == 0:
            break  # No more results

        all_markets.extend(page)
        if len(page) < page_size:
            break  # Last page
        offset += page_size

    print(f"[Polymarket] Fetched {len(all_markets)} total markets across {offset // page_size + 1} pages.")

    crypto_markets = []
    for item in all_markets:
        try:
            if _is_crypto_market(item):
                parsed = parse_market(item)
                if parsed and parsed["id"]:
                    crypto_markets.append(parsed)
        except Exception as e:
            print(f"[Polymarket] Skipping {item.get('id')}: {e}")

    print(f"[Polymarket] Kept {len(crypto_markets)} crypto markets.")
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
