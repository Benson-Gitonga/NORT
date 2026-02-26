# markets.py
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from sqlmodel import Session, select, text
from datetime import datetime

from services.backend.data.database import engine
from services.backend.data.models import Market
from services.backend.core.polymarket import fetch_short_term_crypto_markets, fetch_sports_markets

router = APIRouter(prefix="/markets", tags=["Markets"], redirect_slashes=False)


def sync_markets(session: Session = None):
    """Fetch crypto + sports markets from Polymarket and upsert into DB."""
    crypto_markets = fetch_short_term_crypto_markets(limit=300)
    sports_markets = fetch_sports_markets(limit=300)
    fresh_markets  = crypto_markets + sports_markets

    if not fresh_markets:
        print("[sync] No markets returned from Polymarket.")
        return

    def _do_sync(s):
        # Mark all existing markets inactive first
        existing = s.exec(select(Market)).all()
        for m in existing:
            m.is_active = False
            s.add(m)
        s.commit()

        saved = 0
        for parsed in fresh_markets:
            try:
                if not parsed or not parsed.get("id"):
                    continue
                parsed["category"] = parsed.get("category") or "Crypto"
                parsed["question"] = parsed.get("question") or "Unknown"
                parsed["expires_at"] = parsed.get("expires_at") or datetime(2099, 1, 1)

                existing_market = s.get(Market, str(parsed["id"]))
                if existing_market:
                    existing_market.question      = parsed["question"]
                    existing_market.category      = parsed["category"]
                    # Preserve real previous_odds: save the old current before overwriting
                    existing_market.previous_odds = existing_market.current_odds
                    existing_market.current_odds  = parsed["current_odds"]
                    existing_market.volume        = parsed["volume"]
                    existing_market.avg_volume    = parsed["avg_volume"]
                    existing_market.is_active     = True
                    existing_market.expires_at    = parsed["expires_at"]
                    s.add(existing_market)
                else:
                    # Brand-new market: previous_odds defaults to current_odds
                    # so momentum is 0 until the second sync (correct behaviour —
                    # we have no historical data yet)
                    new_market = parsed.copy()
                    new_market["previous_odds"] = parsed["current_odds"]
                    s.add(Market(**new_market))
                saved += 1
            except Exception as e:
                print(f"[sync] Skipping {parsed.get('id')}: {e}")

        s.commit()
        print(f"[sync] Upserted {saved} crypto + sports markets.")

    if session:
        _do_sync(session)
    else:
        with Session(engine) as s:
            _do_sync(s)


@router.get("/refresh")
def refresh_markets():
    with Session(engine) as session:
        sync_markets(session)
        count = len(session.exec(select(Market).where(Market.is_active == True)).all())
        return {"message": "Markets refreshed", "count": count}


@router.get("/debug-polymarket")
def debug_polymarket():
    """Calls Polymarket directly and shows what the filter returns — no DB write."""
    markets = fetch_short_term_crypto_markets(limit=50)
    return {
        "count": len(markets),
        "sample": [
            {
                "id":       m.get("id"),
                "question": (m.get("question") or "")[:100],
                "category": m.get("category"),
                "volume":   m.get("volume"),
                "odds":     m.get("current_odds"),
            }
            for m in markets[:10]
        ]
    }


@router.get("/")
def get_markets(
    limit: int = 500,
    sort_by: str = "volume",
    category: Optional[str] = Query(default=None, description="Filter by category group: 'crypto' or 'sports'"),
):
    # Categories that belong to each group
    CRYPTO_CATS = {"BTC", "ETH", "SOL", "XRP", "HYPE", "Crypto"}
    SPORTS_CATS = {"NBA", "NHL", "Soccer", "EPL", "La Liga", "Serie A",
                   "Bundesliga", "Ligue 1", "UCL", "MLB", "Tennis", "Golf", "Sports"}

    with Session(engine) as session:
        total = len(session.exec(select(Market)).all())
        if total == 0:
            print("[markets] DB empty — syncing...")
            sync_markets(session)

        statement = select(Market).where(Market.is_active == True)

        if category and category.lower() == "crypto":
            statement = statement.where(Market.category.in_(list(CRYPTO_CATS)))
        elif category and category.lower() == "sports":
            statement = statement.where(Market.category.in_(list(SPORTS_CATS)))

        if sort_by == "volume":
            statement = statement.order_by(Market.volume.desc())
        statement = statement.limit(limit)

        markets = session.exec(statement).all()
        return {
            "markets":   [market_to_response(m) for m in markets],
            "count":     len(markets),
            "cached_at": datetime.utcnow().isoformat(),
        }


@router.get("/{market_id}")
def get_market(market_id: str):
    with Session(engine) as session:
        market = session.get(Market, market_id)
        if not market:
            raise HTTPException(status_code=404, detail=f"Market {market_id} not found")
        return market_to_response(market)


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
