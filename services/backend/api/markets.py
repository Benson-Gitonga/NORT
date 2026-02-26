# markets.py
# Intern 1 — Markets API Routes
# Exposes GET /markets and GET /markets/{id}
# Fetches from Polymarket API and caches in SQLite

from fastapi import APIRouter, HTTPException
from sqlmodel import Session, select
from datetime import datetime
from typing import List

from services.backend.data.database import engine
from services.backend.data.models import Market
from services.backend.core.polymarket import fetch_short_term_crypto_markets, parse_market

router = APIRouter(prefix="/markets", tags=["Markets"], redirect_slashes=False)

# How old cache can be before we re-fetch from Polymarket
CACHE_TTL_MINUTES = 5


# ─────────────────────────────────────────────
# HELPER — is the cache fresh enough?
# ─────────────────────────────────────────────

def cache_is_fresh(session: Session) -> bool:
    try:
        statement = select(Market).limit(1)
        result = session.exec(statement).first()
        return result is not None
    except:
        return False  # Any DB error = cache stale


# ─────────────────────────────────────────────
# HELPER — sync markets from Polymarket into DB
# ─────────────────────────────────────────────

def sync_markets(session: Session):
    """
    Fetches short-term crypto markets (5min/15min/1hr) from Polymarket
    and upserts them into the database.
    """
    fresh_markets = fetch_short_term_crypto_markets(limit=200)

    if not fresh_markets:
        print("[sync] No short-term crypto markets returned from Polymarket.")
        return

    for parsed in fresh_markets:
        try:
            if not parsed or not parsed["id"]:
                continue

            existing = session.get(Market, parsed["id"])
            if existing:
                existing.previous_odds = existing.current_odds
                existing.current_odds  = parsed["current_odds"]
                existing.volume        = parsed["volume"]
                existing.avg_volume    = (existing.avg_volume * 0.8) + (parsed["volume"] * 0.2)
                existing.is_active     = parsed["is_active"]
                session.add(existing)
            else:
                market = Market(**parsed)
                session.add(market)

        except Exception as e:
            print(f"[sync] Skipping market {parsed.get('id')}: {e}")
            continue

    session.commit()
    print(f"[sync] Synced {len(fresh_markets)} short-term crypto markets.")


# ─────────────────────────────────────────────
# GET /markets
# Returns all active cached markets
# Refreshes cache from Polymarket if stale
# ─────────────────────────────────────────────

# Remove duplicate @router.get("/markets") at bottom - KEEP ONLY THIS:

@router.get("/")
def get_markets(
    limit: int = 20,
    sort_by: str = "volume"
):
    with Session(engine) as session:
        if not cache_is_fresh(session):
            print("Cache empty — syncing from Polymarket...")
            sync_markets(session)

        statement = select(Market).where(Market.is_active == True)
        if sort_by == "volume":
            statement = statement.order_by(Market.volume.desc())
        elif sort_by == "avg_volume":
            statement = statement.order_by(Market.avg_volume.desc())
        statement = statement.limit(limit)

        markets = session.exec(statement).all()
        return {
            "markets": [market_to_response(m) for m in markets],
            "count": len(markets),
            "cached_at": datetime.utcnow().isoformat()
        }


@router.get("/refresh")
def refresh_markets():
    with Session(engine) as session:
        sync_markets(session)
        count_stmt = select(Market).where(Market.is_active == True)
        count = len(session.exec(count_stmt).all())
        return {"message": "Markets refreshed", "count": count}


@router.get("/debug-polymarket")
def debug_polymarket():
    """Hits Polymarket API directly — shows raw response for debugging."""
    import httpx, os
    url = f"{os.getenv('POLYMARKET_API_URL', 'https://gamma-api.polymarket.com')}/markets"
    # Fetch 50 sorted by volume, show which ones pass the crypto filter
    params = {"active": "true", "closed": "false", "limit": 50, "sort_by": "volume24hr", "ascending": "false"}
    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.get(url, params=params)
            raw = r.json()
    except Exception as e:
        return {"error": str(e)}

    from services.backend.core.polymarket import _is_crypto_market
    items = raw if isinstance(raw, list) else raw.get("markets") or raw.get("data") or []
    crypto_hits = [i for i in items if _is_crypto_market(i)]

    return {
        "total_fetched": len(items),
        "crypto_matches": len(crypto_hits),
        "all_categories": list(set(i.get("category") for i in items)),
        "crypto_sample": [
            {"id": i.get("id"), "question": (i.get("question") or "")[:80], "volume24hr": i.get("volume24hr")}
            for i in crypto_hits[:10]
        ],
        "non_crypto_sample": [
            {"id": i.get("id"), "question": (i.get("question") or "")[:80]}
            for i in items[:5] if not _is_crypto_market(i)
        ]
    }


@router.get("/{market_id}")
def get_market(market_id: str):
    with Session(engine) as session:
        market = session.get(Market, market_id)
        if not market:
            raise HTTPException(status_code=404, detail=f"Market {market_id} not found")
        return market_to_response(market)


# ─────────────────────────────────────────────
# HELPER — clean response format
# ─────────────────────────────────────────────

def market_to_response(market: Market) -> dict:
    return {
        "id":            market.id,
        "question":      market.question,
        "category":      market.category,
        "current_odds":  market.current_odds,
        "previous_odds": market.previous_odds,
        "volume":        market.volume,
        "avg_volume":    market.avg_volume,
        "is_active":     market.is_active,
        "expires_at":    str(market.expires_at),
    }


