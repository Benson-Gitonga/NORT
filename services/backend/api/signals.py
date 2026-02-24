from datetime import datetime

from fastapi import APIRouter
from sqlmodel import Session
from sqlalchemy.orm import Session
from services.backend.data.database import engine
from services.backend.data.models import AISignal

router = APIRouter(prefix="/signals", tags=["Signals"])
from services.backend.data.models import Market, AISignal
from services.backend.core.signals_engine import rank_markets

#fastApi router
router = APIRouter(prefix="/signals", tags=["Signals"], redirect_slashes=False)

@router.get("/")
def get_top_signals(top: int = 20):
    with Session(engine) as session:
        signals = session.query(AISignal).distinct(AISignal.market_id)\
                        .order_by(AISignal.confidence_score.desc()).limit(top).all()
        return [{"market_id": s.market_id, "score": s.confidence_score, "reason": s.analysis_summary} for s in signals]


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
