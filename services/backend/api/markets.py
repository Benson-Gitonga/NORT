# markets.py
# Intern 1 — Markets API Routes
# Exposes GET /markets and GET /markets/{id}
# Fetches from Polymarket API and caches in SQLite

from fastapi import APIRouter, HTTPException
from sqlmodel import Session, select
from datetime import datetime, timedelta
from typing import List
from sqlalchemy.orm import Session

from services.backend.data.database import engine
from services.backend.data.models import Market
from services.backend.core.polymarket import fetch_markets, parse_market
import httpx
import os

router = APIRouter(prefix="/markets", tags=["Markets"], redirect_slashes=False)

# How old cache can be before we re-fetch from Polymarket
CACHE_TTL_MINUTES = 5


# ─────────────────────────────────────────────
# HELPER — is the cache fresh enough?
# ─────────────────────────────────────────────

def cache_is_fresh(session: Session) -> bool:
    try:
        # SQLModel/SQLAlchemy 2.0 syntax
        statement = select(Market).order_by(Market.expires_at.desc()).limit(1)
        result = session.execute(statement)
        latest = result.scalar_one_or_none()
        return latest is not None
    except:
        return False  # Any DB error = cache stale


# ─────────────────────────────────────────────
# HELPER — sync markets from Polymarket into DB
# ─────────────────────────────────────────────

def sync_markets(session: Session):
    """
    Fetches fresh markets from Polymarket API and upserts into SQLite.
    Called when cache is stale or empty.
    """
    url = f"{os.getenv('POLYMARKET_API_URL', 'https://gamma-api.polymarket.com')}/markets"
    params = {"active": "true", "closed": "false", "limit": 100}

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            raw_markets = response.json()
    except Exception as e:
        print(f"Polymarket API error: {e}")
        return  # fail silently — return cached data if available

    import json
    for item in raw_markets:
        try:
            parsed = parse_market(item)
            if not parsed or not parsed["id"]:
                continue

            # Check if market already exists
            existing = session.get(Market, parsed["id"])

            if existing:
                # Save current price as previous before updating
                # This is what powers momentum scoring
                existing.previous_odds = existing.current_odds
                existing.current_odds  = parsed["current_odds"]
                existing.volume        = parsed["volume"]
                # Rolling average: 80% old + 20% new keeps baseline stable
                existing.avg_volume    = (existing.avg_volume * 0.8) + (parsed["volume"] * 0.2)
                existing.is_active     = parsed["is_active"]
                session.add(existing)
            else:
                # New market — insert it
                market = Market(**parsed)
                session.add(market)

        except Exception as e:
            print(f"Skipping market {item.get('id')}: {e}")
            continue

    session.commit()


# ─────────────────────────────────────────────
# GET /markets
# Returns all active cached markets
# Refreshes cache from Polymarket if stale
# ─────────────────────────────────────────────

# Remove duplicate @router.get("/markets") at bottom - KEEP ONLY THIS:

@router.get("/")  # This becomes /markets/

@router.get("/")
def get_markets():
    with Session(engine) as session:
        if not cache_is_fresh(session):
            print("Cache empty — syncing from Polymarket...")
            sync_markets(session)

        statement = select(Market).where(Market.is_active == True)
        markets = session.exec(statement).all()
        return {
            "markets": [market_to_response(m) for m in markets],
            "count": len(markets),
            "cached_at": datetime.utcnow().isoformat()
        }

@router.get("/{market_id}")
def get_market(market_id: str):
    with Session(engine) as session:
        market = session.get(Market, market_id)
        if not market:
            raise HTTPException(status_code=404, detail=f"Market {market_id} not found")
        return market_to_response(market)

@router.get("/refresh")
def refresh_markets():
    with Session(engine) as session:
        sync_markets(session)
        return {"message": "Markets refreshed"}

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

