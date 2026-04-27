# polymarket.py
# Fetches active markets from Polymarket's Gamma API.
#
# The API has two relevant endpoints:
#   GET /markets  — individual markets, filters: active, closed, limit, tag_id, volume_num_min, etc.
#   GET /events   — grouped events, filters: active, closed, limit, tag_id, tag_slug, etc.
#
# Previous version was broken because:
#   1. It called /events with slug= and tag_slug= params that no longer return data
#   2. The slug-prefix strategy (btc-updown, etc.) was never reliably supported
#   3. tag_slug= on /events returned 404 for all tags
#
# Current strategy (what actually works):
#   1. Hit GET /events with tag_id for crypto/sports — events nest their markets inside
#   2. Fall back to GET /markets?active=true broad fetch if tag queries return nothing
#   3. Classify results using question text and tag names we already have

import httpx
import os
import json
from datetime import datetime
from typing import List, Dict, Optional

GAMMA_API = os.getenv("POLYMARKET_API_URL", "https://gamma-api.polymarket.com")

MIN_TRADEABLE_ODDS = 0.05
MAX_TRADEABLE_ODDS = 0.95

CRYPTO_TAGS = {
    "crypto", "crypto-prices", "bitcoin", "ethereum", "solana",
    "xrp", "hyperliquid", "megaeth", "stablecoins", "etf", "defi",
}

SPORT_LABELS = {
    "nba": "NBA", "basketball": "NBA", "nba-finals": "NBA", "nba-champion": "NBA",
    "hockey": "NHL", "nhl": "NHL", "stanley-cup": "NHL",
    "soccer": "Soccer", "fifa-world-cup": "Soccer", "2026-fifa-world-cup": "Soccer",
    "world-cup": "Soccer", "epl": "EPL", "la-liga": "La Liga",
    "serie-a": "Serie A", "bundesliga": "Bundesliga", "ligue-1": "Ligue 1",
    "champions-league": "UCL", "ucl": "UCL",
    "baseball": "MLB", "mlb": "MLB",
    "tennis": "Tennis", "golf": "Golf", "sports": "Sports",
}

COIN_LABELS = {
    "btc": "BTC", "bitcoin": "BTC",
    "eth": "ETH", "ethereum": "ETH",
    "sol": "SOL", "solana": "SOL",
    "xrp": "XRP",
    "hyperliquid": "HYPE",
    "megaeth": "ETH",
    "doge": "DOGE", "dogecoin": "DOGE",
    "bnb": "BNB", "avax": "AVAX", "avalanche": "AVAX",
    "link": "LINK", "chainlink": "LINK",
    "ada": "ADA", "cardano": "ADA",
}


def _get_coin_label(text: str) -> str:
    t = text.lower()
    for key, label in COIN_LABELS.items():
        if key in t:
            return label
    return "Crypto"


def _get_sport_label(tags: list) -> str:
    slugs = [t.get("slug", "") for t in tags]
    for slug in slugs:
        if slug in SPORT_LABELS:
            return SPORT_LABELS[slug]
    return "Sports"


def _is_crypto(tags: list) -> bool:
    slugs = {t.get("slug", "") for t in tags}
    return bool(slugs & CRYPTO_TAGS)


def _is_sports(tags: list) -> bool:
    slugs = {t.get("slug", "") for t in tags}
    return "sports" in slugs


# ─── LOW LEVEL FETCHERS ──────────────────────────────────────────────────────

def _fetch_events(params: dict) -> List[Dict]:
    """
    GET /events — returns event objects that contain nested markets[].
    Correct params: active, closed, limit, offset, tag_id, tag_slug,
                    volume_min, volume_max, _sort, _order
    NOTE: tag_slug works on /events but requires exact tag slug strings
    that Polymarket currently has active. Use tag_id for reliability.
    """
    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.get(f"{GAMMA_API}/events", params=params)
            r.raise_for_status()
            data = r.json()
            return data if isinstance(data, list) else (data.get("events") or data.get("data") or [])
    except Exception as e:
        print(f"[Polymarket] /events fetch error (params={params}): {e}")
        return []


def _fetch_markets(params: dict) -> List[Dict]:
    """
    GET /markets — returns flat market objects directly (no event nesting).
    Correct params: active, closed, limit, offset, tag_id,
                    volume_num_min, end_date_min, _sort, _order
    This is the reliable fallback — always returns data when active=true.
    """
    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.get(f"{GAMMA_API}/markets", params=params)
            r.raise_for_status()
            data = r.json()
            return data if isinstance(data, list) else (data.get("markets") or data.get("data") or [])
    except Exception as e:
        print(f"[Polymarket] /markets fetch error (params={params}): {e}")
        return []


# ─── CRYPTO MARKETS ──────────────────────────────────────────────────────────

def fetch_short_term_crypto_markets(limit: int = 300) -> List[Dict]:
    """
    Fetch active crypto markets from Polymarket.

    Strategy:
      1. GET /events?tag_slug=crypto — events with nested markets (best for grouped data)
      2. GET /events?tag_slug=crypto-prices — ETF, FDV, price-range markets
      3. Fallback: GET /markets?active=true&volume_num_min=100 — broad fetch,
         classify by question text — used when tag queries return nothing
    """
    all_markets: List[Dict] = []
    seen_ids: set = set()

    def _add(m: Dict):
        mid = m.get("id")
        if mid and mid not in seen_ids:
            seen_ids.add(mid)
            all_markets.append(m)

    # Source 1: /events with crypto tag_slug
    for tag in ["crypto", "crypto-prices"]:
        events = _fetch_events({
            "active":   "true",
            "closed":   "false",
            "limit":    100,
            "tag_slug": tag,
            "_sort":    "volume24hr",
            "_order":   "desc",
        })
        for ev in events:
            if not _is_crypto(ev.get("tags") or []):
                continue
            for m in _extract_markets_from_event(ev):
                _add(m)

    # Source 2: /markets direct with high-volume filter (reliable, no tag required)
    if len(all_markets) < 20:
        print(f"[Polymarket] Tag query returned {len(all_markets)} markets — using broad /markets fallback")
        raw_markets = _fetch_markets({
            "active":        "true",
            "closed":        "false",
            "limit":         500,
            "volume_num_min": 100,
            "_sort":         "volume24hr",
            "_order":        "desc",
        })
        for item in raw_markets:
            # Classify by question text — keep crypto-sounding ones
            q = (item.get("question") or "").lower()
            tags = item.get("tags") or []
            if _is_crypto(tags) or any(k in q for k in COIN_LABELS):
                parsed = _parse_flat_market(item)
                if parsed:
                    _add(parsed)

    # Source 3: truly broad fallback — grab everything active and high volume
    if len(all_markets) < 10:
        print(f"[Polymarket] Crypto markets still low ({len(all_markets)}) — broad volume fallback")
        raw_markets = _fetch_markets({
            "active":        "true",
            "closed":        "false",
            "limit":         300,
            "volume_num_min": 500,
            "_sort":         "volume24hr",
            "_order":        "desc",
        })
        for item in raw_markets:
            parsed = _parse_flat_market(item)
            if parsed:
                _add(parsed)

    print(f"[Polymarket] Total crypto markets collected: {len(all_markets)}")
    all_markets.sort(key=lambda m: m.get("volume", 0), reverse=True)
    return all_markets[:limit]


# ─── SPORTS MARKETS ──────────────────────────────────────────────────────────

def fetch_sports_markets(limit: int = 300) -> List[Dict]:
    """
    Fetch active sports markets from Polymarket.

    Strategy:
      1. GET /events?tag_slug=sports — events with nested markets
      2. Fallback: GET /markets broad fetch + classify by tags
    """
    all_markets: List[Dict] = []
    seen_ids: set = set()

    def _add(m: Dict):
        mid = m.get("id")
        if mid and mid not in seen_ids:
            seen_ids.add(mid)
            all_markets.append(m)

    events = _fetch_events({
        "active":   "true",
        "closed":   "false",
        "limit":    100,
        "tag_slug": "sports",
        "_sort":    "volume24hr",
        "_order":   "desc",
    })
    for ev in events:
        if not _is_sports(ev.get("tags") or []):
            continue
        sport_label = _get_sport_label(ev.get("tags") or [])
        for m in _extract_markets_from_event(ev, category_override=sport_label):
            _add(m)

    # Fallback: broad /markets fetch, classify by tags
    if len(all_markets) < 10:
        print(f"[Polymarket] Sports events returned {len(all_markets)} — using /markets fallback")
        raw_markets = _fetch_markets({
            "active":        "true",
            "closed":        "false",
            "limit":         300,
            "volume_num_min": 100,
            "_sort":         "volume24hr",
            "_order":        "desc",
        })
        for item in raw_markets:
            tags = item.get("tags") or []
            if _is_sports(tags):
                sport_label = _get_sport_label(tags)
                parsed = _parse_flat_market(item, category_override=sport_label)
                if parsed:
                    _add(parsed)

    print(f"[Polymarket] Total sports markets collected: {len(all_markets)}")
    all_markets.sort(key=lambda m: m.get("volume", 0), reverse=True)
    return all_markets[:limit]


# ─── PARSERS ─────────────────────────────────────────────────────────────────

def _extract_markets_from_event(event: Dict, category_override: str = None) -> List[Dict]:
    """Extract child markets from an /events response item."""
    results = []
    event_title = event.get("title") or ""
    event_v24   = event.get("volume24hr") or 0
    event_v1wk  = event.get("volume1wk") or 0
    for m in (event.get("markets") or []):
        if not m.get("question"):
            m["question"] = event_title
        parsed = _parse_market_item(m, event_title, event_v24, event_v1wk, category_override)
        if parsed:
            results.append(parsed)
    return results


def _parse_flat_market(item: Dict, category_override: str = None) -> Optional[Dict]:
    """Parse a market returned directly from /markets (flat, no event wrapper)."""
    return _parse_market_item(item, "", 0, 0, category_override)


def _parse_market_item(
    item: Dict,
    event_title: str = "",
    event_v24: float = 0,
    event_v1wk: float = 0,
    category_override: str = None,
) -> Optional[Dict]:
    """Convert a raw Polymarket market item into our Market schema dict."""
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
        if not (0.0 <= current_odds <= 1.0):
            current_odds = 0.5
    except Exception:
        current_odds = 0.5

    # Drop near-resolved markets — no trading value
    if current_odds < MIN_TRADEABLE_ODDS or current_odds > MAX_TRADEABLE_ODDS:
        return None

    # Parse expiry
    try:
        end_str = item.get("endDate") or item.get("endDateIso") or ""
        expires_at = datetime.fromisoformat(end_str.replace("Z", "+00:00")) if end_str else datetime(2099, 1, 1)
    except Exception:
        expires_at = datetime(2099, 1, 1)

    # Volume: market-level 24hr, fall back to event-level
    volume24hr = float(item.get("volume24hr") or event_v24 or 0)
    volume1wk  = float(item.get("volume1wk")  or event_v1wk or 0)
    avg_volume = (volume1wk / 7.0) if volume1wk > 0 else max(volume24hr, 1.0)

    # Category: use override (sports label), else classify from tags, else question text
    if category_override:
        category = category_override
    else:
        item_tags = item.get("tags") or []
        if _is_sports(item_tags):
            category = _get_sport_label(item_tags)
        elif _is_crypto(item_tags):
            category = _get_coin_label(question)
        else:
            category = _get_coin_label(question)

    return {
        "id":            market_id,
        "question":      question,
        "category":      category,
        "current_odds":  current_odds,
        "previous_odds": None,   # markets.py upsert preserves real previous on update
        "volume":        volume24hr,
        "avg_volume":    avg_volume,
        "is_active":     bool(item.get("active", True)),
        "expires_at":    expires_at,
    }


# Keep old name as alias so any other code that imports it still works
parse_market = _parse_market_item


# ─── market-p: PRICE HISTORY ─────────────────────────────────────────────────
# Fetches historical YES price data for a market from Polymarket's CLOB API.
# Flow: condition_id → token_id (via Gamma API) → price history (via CLOB API)
# The CLOB API uses token_id (clobTokenIds[0]) not the condition ID stored in our DB.

CLOB_API = "https://clob.polymarket.com"

# market-p2: Fidelity = minutes between each data point.
# Lower = more granular (more points) but less reliable on Render's slow outbound.
# These values are tuned to return ~150-180 points per interval reliably.
_FIDELITY_MAP = {
    "1d":  10,   # every 10 min  → ~144 points
    "1w":  60,   # every 1 hour  → ~168 points
    "1m":  240,  # every 4 hours → ~180 points
    "6m":  720,  # every 12 hours → ~180 points
    "1y":  1440, # every 24 hours → ~365 points
    "all": 1440,
}
# market-p2: Fallback fidelity if primary call returns empty.
# 720 (12hr) is known to be the most reliable granularity on Polymarket's CLOB.
_FIDELITY_FALLBACK = 720


def _fetch_clob_prices(yes_token_id: str, interval: str, fidelity: int) -> list:
    """
    market-p2: Inner helper — calls CLOB /prices-history for a given token + fidelity.
    Returns raw history list or [] on any failure.
    """
    try:
        with httpx.Client(timeout=20.0) as client:  # market-p2: raised from 10s for Render cold starts
            clob_res = client.get(
                f"{CLOB_API}/prices-history",
                params={
                    "market":   yes_token_id,
                    "interval": interval,
                    "fidelity": fidelity,
                }
            )
            clob_res.raise_for_status()
            return clob_res.json().get("history", [])
    except Exception as e:
        print(f"[market-p2] CLOB fetch failed (token={yes_token_id}, fidelity={fidelity}): {e}")
        return []


def fetch_price_history(market_id: str, interval: str = "1w", fidelity: int = None) -> list:
    """
    market-p: Given a Polymarket condition ID (what we store as market.id),
    resolve the YES token_id then return price history as a list of floats (0-100).
    Returns empty list if anything fails — frontend falls back to placeholder.
    market-p2: fidelity now defaults to None — picked automatically from _FIDELITY_MAP
    per interval, with a 720-min fallback retry if the primary call returns empty.
    """
    try:
        # market-p3: resolve token_id from Gamma ID directly to avoid categorical market collisions
        with httpx.Client(timeout=20.0) as client:
            gamma_res = client.get(f"{GAMMA_API}/markets/{market_id}")
            gamma_res.raise_for_status()
            raw = gamma_res.json()

        if not raw:
            print(f"[market-p] No Gamma market found for ID: {market_id}")
            return []

        # market-p: clobTokenIds is a JSON string like '["0xabc...", "0xdef..."]'
        # Index 0 = YES token, index 1 = NO token
        clob_token_ids_raw = raw.get("clobTokenIds", "[]")
        if isinstance(clob_token_ids_raw, str):
            clob_token_ids = json.loads(clob_token_ids_raw)
        else:
            clob_token_ids = clob_token_ids_raw

        if not clob_token_ids:
            print(f"[market-p] No clobTokenIds for market: {market_id}")
            return []

        yes_token_id = clob_token_ids[0]  # market-p: YES token is always index 0

        # market-p2: Pick fidelity from map if not explicitly passed
        chosen_fidelity = fidelity if fidelity is not None else _FIDELITY_MAP.get(interval, 60)

        # market-p: Step 2 — fetch price history from CLOB API using YES token_id
        history = _fetch_clob_prices(yes_token_id, interval, chosen_fidelity)

        # market-p2: If primary call returns empty and fidelity was granular, retry at fallback
        if not history and chosen_fidelity < _FIDELITY_FALLBACK:
            print(f"[market-p2] Empty at fidelity={chosen_fidelity}, retrying at {_FIDELITY_FALLBACK} for token: {yes_token_id}")
            history = _fetch_clob_prices(yes_token_id, interval, _FIDELITY_FALLBACK)

        # market-p: Response shape: { "history": [{ "t": timestamp, "p": price }, ...] }
        if not history:
            print(f"[market-p] Empty price history for token: {yes_token_id}")
            return []

        # market-p: Convert decimal prices (0.0-1.0) to cents (0-100) for the chart
        prices = [round(float(point["p"]) * 100, 1) for point in history if "p" in point]
        print(f"[market-p] Got {len(prices)} price points for market {market_id}")
        return prices

    except Exception as e:
        print(f"[market-p] fetch_price_history failed for {market_id}: {e}")
        return []
# ─── end market-p ─────────────────────────────────────────────────────────────
