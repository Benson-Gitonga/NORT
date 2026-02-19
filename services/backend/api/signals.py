# signals.py
# Intern 2 — Signals API Route
# Exposes GET /signals?top=20
# Calls signals_engine.py for all the math/logic.

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import List
from datetime import datetime

from services.backend.data.database import engine
from services.backend.data.models import Market, AISignal
from services.backend.core.signals_engine import rank_markets

router = APIRouter(prefix="/signals", tags=["Signals"])


# ─────────────────────────────────────────────
# HELPER: convert Market DB rows → plain dicts
# signals_engine.py works with plain dicts,
# not SQLModel objects — this bridges the gap.
# ─────────────────────────────────────────────

def market_to_dict(market: Market) -> dict:
    return {
        "id":           market.id,
        "question":     market.question,
        "category":     market.category,
        "current_odds": market.current_odds,
        "is_active":    market.is_active,
        "expires_at":   market.expires_at,
        # These two fields power the scoring.
        # previous_odds: ideally from last snapshot — defaulting to current for now.
        # avg_volume:    ideally a rolling average — defaulting to a baseline.
        # Intern 1 can enrich these fields later when more data is available.
        "previous_odds": getattr(market, "previous_odds", market.current_odds),
        "volume":        getattr(market, "volume", 1000),
        "avg_volume":    getattr(market, "avg_volume", 500),
    }


# ─────────────────────────────────────────────
# GET /signals?top=20
# Returns top N ranked markets with scores and reasons.
# Used by: Telegram /signals command, Dashboard Signals page, OpenClaw agent
# ─────────────────────────────────────────────

@router.get("/")
def get_signals(top: int = 20):
    """
    Returns the top ranked prediction markets based on:
    - Momentum (price movement)
    - Volume spike (unusual activity)
    - Liquidity filter (removes thin markets)

    Each result includes a plain-English 'reason' field.
    """
    with Session(engine) as session:
        # Fetch only active markets from the database
        statement = select(Market).where(Market.is_active == True)
        markets = session.exec(statement).all()

        if not markets:
            return {
                "signals": [],
                "count": 0,
                "message": "No active markets found. Intern 1 needs to populate the markets table."
            }

        # Convert to dicts and run through the signals engine
        market_dicts = [market_to_dict(m) for m in markets]
        ranked = rank_markets(market_dicts, top=top)

        # Save snapshot to DB so Dashboard and OpenClaw have history
        save_signal_snapshot(session, ranked)

        return {
            "signals": ranked,
            "count": len(ranked),
            "generated_at": datetime.utcnow().isoformat()
        }


# ─────────────────────────────────────────────
# HELPER: Save signals snapshot to AISignal table
# This gives the Dashboard historical data
# and gives the volume scorer a baseline over time.
# ─────────────────────────────────────────────

def save_signal_snapshot(session: Session, ranked: list):
    """
    Saves the current top signals into the AISignal table.
    Intern 6 (Dashboard) reads from this table for the Signals page.
    Intern 3 (OpenClaw) calls get_signals() which hits this endpoint.
    """
    for signal in ranked:
        snapshot = AISignal(
            market_id=signal["market_id"],
            prediction="N/A",               # OpenClaw fills this — we just store the score
            confidence_score=signal["score"],
            analysis_summary=signal["reason"],
            timestamp=datetime.utcnow()
        )
        session.add(snapshot)

    session.commit()
