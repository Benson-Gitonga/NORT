# polymarket.py
# Fetches crypto markets from Polymarket Events API (tag_slug=crypto)
# Then filters to only markets that mention specific crypto coins by name

import httpx
import os
import json
from datetime import datetime
from typing import List, Dict, Optional

GAMMA_API = os.getenv("POLYMARKET_API_URL", "https://gamma-api.polymarket.com")

# Coins to look for in market question text
# Add any coin here and it will automatically be picked up
CRYPTO_COINS = [
    "bitcoin", "btc",
    "ethereum", "eth",
    "solana", "sol",
    "xrp", "ripple",
    "dogecoin", "doge",
    "bnb",
    "avax", "avalanche",
    "hyperliquid", "hype",
    "sui",
    "cardano", "ada",
    "chainlink",
    "polygon", "matic",
    "pepe",
    "shiba", "shib",
    "ton", "toncoin",
    "near",
    "injective", "inj",
    "arbitrum", "arb",
    "sei",
    "aptos", "apt",
    "crypto", "cryptocurrency",
    "altcoin", "defi",
    "stablecoin", "usdc", "usdt",
    "coinbase", "binance", "kraken",
    "microstrategy", "mstr",
    "blackrock bitcoin", "spot etf", "bitcoin etf",
]


def _get_coin_label(question: str) -> Optional[str]:
    """
    Returns the first coin matched in the question, or None if no match.
    Used both for filtering AND for the category label on the card.
    """
    q = question.lower()
    for coin in CRYPTO_COINS:
        if coin in q:
            # Return a clean display label
            labels = {
                "btc": "BTC", "bitcoin": "BTC",
                "eth": "ETH", "ethereum": "ETH",
                "sol": "SOL", "solana": "SOL",
                "xrp": "XRP", "ripple": "XRP",
                "doge": "DOGE", "dogecoin": "DOGE",
                "bnb": "BNB",
                "avax": "AVAX", "avalanche": "AVAX",
                "hyperliquid": "HYPE", "hype": "HYPE",
                "sui": "SUI",
                "ada": "ADA", "cardano": "ADA",
                "chainlink": "LINK",
                "matic": "MATIC", "polygon": "MATIC",
                "pepe": "PEPE",
                "shib": "SHIB", "shiba": "SHIB",
                "ton": "TON", "toncoin": "TON",
                "near": "NEAR",
                "inj": "INJ", "injective": "INJ",
                "arb": "ARB", "arbitrum": "ARB",
                "sei": "SEI",
                "apt": "APT", "aptos": "APT",
            }
            return labels.get(coin, "Crypto")
    return None


def fetch_short_term_crypto_markets(limit: int = 300) -> List[Dict]:
    """
    1. Fetch events with tag_slug=crypto from Polymarket
    2. Extract all child markets from those events
    3. Keep only markets whose question mentions a specific coin
    """
    url = f"{GAMMA_API}/events"
    all_markets = []
    offset = 0

    while True:
        params = {
            "active":   "true",
            "closed":   "false",
            "limit":    50,
            "offset":   offset,
            "tag_slug": "crypto",
        }
        try:
            with httpx.Client(timeout=15.0) as client:
                r = client.get(url, params=params)
                r.raise_for_status()
                data = r.json()
        except Exception as e:
            print(f"[Polymarket] Events API error at offset {offset}: {e}")
            break

        if isinstance(data, dict):
            data = data.get("events") or data.get("data") or []
        if not isinstance(data, list) or len(data) == 0:
            break

        for event in data:
            event_title = event.get("title") or ""
            event_markets = event.get("markets") or []
            for m in event_markets:
                # Use event title if market question is missing
                if not m.get("question"):
                    m["question"] = event_title
                parsed = parse_market(m)
                if parsed and parsed["id"]:
                    all_markets.append(parsed)

        print(f"[Polymarket] Page offset={offset}: {len(data)} events fetched.")
        if len(data) < 50 or len(all_markets) >= limit:
            break
        offset += 50

    # Filter to only markets that mention a specific coin
    coin_markets = [m for m in all_markets if m.get("category") != "Crypto-General"]
    # (parse_market sets category="Crypto-General" when no coin matched — filter those out)
    # Actually filter by checking _get_coin_label on question
    filtered = [m for m in all_markets if _get_coin_label(m["question"]) is not None]

    print(f"[Polymarket] Total: {len(all_markets)} crypto markets, {len(filtered)} with specific coin mentions.")
    return filtered if filtered else all_markets  # fallback: return all if filter too strict


def parse_market(item: Dict) -> Optional[Dict]:
    """Converts a raw Polymarket market item to our Market schema dict."""
    market_id = item.get("id") or item.get("conditionId") or ""
    if not market_id:
        return None

    question = item.get("question") or "Unknown"

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

    # Label the category as the coin name (BTC, ETH, SOL etc.)
    coin_label = _get_coin_label(question) or "Crypto"

    return {
        "id":            str(market_id),
        "question":      question,
        "category":      coin_label,
        "current_odds":  current_odds,
        "previous_odds": current_odds,
        "volume":        volume24hr,
        "avg_volume":    avg_volume,
        "is_active":     bool(item.get("active", True)),
        "expires_at":    expires_at,
    }
