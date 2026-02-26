from datetime import datetime
from fastapi import APIRouter
from sqlmodel import Session, select
from services.backend.data.database import engine
from services.backend.data.models import Market, AISignal
from services.backend.core.signals_engine import rank_markets

router = APIRouter(prefix="/signals", tags=["Signals"], redirect_slashes=False)


@router.get("/")
def get_top_signals(top: int = 20):
    with Session(engine) as session:

        # Build market lookup map for enrichment
        market_stmt = select(Market).where(Market.is_active == True)
        markets = session.exec(market_stmt).all()
        market_map = {m.id: m for m in markets}

        # Try stored AISignal snapshots first
        statement = select(AISignal).order_by(AISignal.confidence_score.desc()).limit(top)
        signals = session.exec(statement).all()

        if signals:
            result = []
            for s in signals:
                m = market_map.get(s.market_id)
                result.append({
                    "market_id":    s.market_id,
                    "score":        s.confidence_score,
                    "reason":       s.analysis_summary,
                    # Enriched market fields so frontend doesn't need a second fetch
                    "question":     m.question      if m else "Unknown market",
                    "category":     m.category      if m else "crypto",
                    "current_odds": m.current_odds  if m else 0.5,
                    "volume":       m.volume        if m else 0.0,
                })
            return result

        # Fallback: no snapshots yet — run engine live
        market_dicts = [
            {
                "id":            m.id,
                "question":      m.question,
                "category":      m.category,
                "current_odds":  m.current_odds,
                "previous_odds": m.previous_odds,
                "volume":        m.volume,
                "avg_volume":    m.avg_volume,
                "expires_at":    m.expires_at,
            }
            for m in markets
        ]

        if not market_dicts:
            return []

        ranked = rank_markets(market_dicts, top=top)
        save_signal_snapshot(session, ranked)

        # Enrich ranked results with market fields
        result = []
        for s in ranked:
            m = market_map.get(s.get("market_id") or s.get("id"))
            result.append({
                "market_id":    s.get("market_id") or s.get("id"),
                "score":        s.get("score", 0),
                "reason":       s.get("reason", ""),
                "question":     m.question      if m else s.get("question", "Unknown market"),
                "category":     m.category      if m else "crypto",
                "current_odds": m.current_odds  if m else 0.5,
                "volume":       m.volume        if m else 0.0,
            })
        return result


def save_signal_snapshot(session: Session, ranked: list):
    for signal in ranked:
        snapshot = AISignal(
            market_id=signal.get("market_id") or signal.get("id"),
            prediction="N/A",
            confidence_score=signal.get("score", 0),
            analysis_summary=signal.get("reason", ""),
            timestamp=datetime.utcnow(),
        )
        session.add(snapshot)
    session.commit()
