# polymarket.py
# Intern 1 — Polymarket API Client
# Fetches market data from the Polymarket Gamma API
# Called by markets.py to populate the database

import httpx
import os
from datetime import datetime
from typing import List, Dict

POLYMARKET_API_URL = os.getenv("POLYMARKET_API_URL", "https://gamma-api.polymarket.com")

async def fetch_markets(limit: int = 100) -> List[Dict]:
    """
    Fetches active markets from the Polymarket Gamma API.
    Returns a list of market dicts ready to be saved to the database.
    """
    url = f"{POLYMARKET_API_URL}/markets"
    params = {
        "active": "true",
        "closed": "false",
        "limit": limit,
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        data = response.json()

    markets = []
    for item in data:
        try:
            market = parse_market(item)
            if market:
                markets.append(market)
        except Exception:
            continue  # skip malformed entries

    return markets


def parse_market(item: Dict) -> Dict:
    """
    Converts a raw Polymarket API response item
    into a clean dict matching the Market table schema.
    """
    # Polymarket returns prices as a stringified list e.g. "0.72"
    # We take the first outcome's price as current_odds
    try:
        outcomes = item.get("outcomePrices", "[]")
        if isinstance(outcomes, str):
            import json
            outcomes = json.loads(outcomes)
        current_odds = float(outcomes[0]) if outcomes else 0.5
    except Exception:
        current_odds = 0.5

    # Parse expiry date
    try:
        expires_at = datetime.fromisoformat(
            item.get("endDate", "").replace("Z", "+00:00")
        )
    except Exception:
        expires_at = datetime(2099, 1, 1)  # fallback far future date

    volume24hr = float(item.get("volume24hr", 0) or 0)
    volume1wk  = float(item.get("volume1wk", 0) or 0)

    # Daily average = weekly volume divided by 7
    # If no weekly data, use 24hr volume as baseline
    avg_volume = (volume1wk / 7) if volume1wk > 0 else volume24hr

    # Avoid division by zero in signals engine
    if avg_volume == 0:
        avg_volume = 1.0

    return {
        "id":            item.get("id", ""),
        "question":      item.get("question", "Unknown"),
        "category":      item.get("category", "general"),
        "current_odds":  current_odds,
        "previous_odds": current_odds,
        "volume":        volume24hr,
        "avg_volume":    avg_volume,
        "is_active":     item.get("active", True),
        "expires_at":    expires_at,
    }
