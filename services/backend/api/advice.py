import json
import httpx
from fastapi import APIRouter, HTTPException
from sqlmodel import Session, select
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from services.backend.data.database import engine
from services.backend.data.models import Market, AISignal, Trade, User
from services.agent.prompt_templates import (
    ADVICE_SYSTEM_PROMPT,
    ADVICE_USER_PROMPT,
    PREMIUM_ADVICE_USER_PROMPT,
)

router = APIRouter(prefix="/agent", tags=["Agent"])

OPENCLAW_URL = "http://192.168.100.15:18789/api/agent/turn"


# ── Request / Response Models ─────────────────────────────────────────────────

class AdviceRequest(BaseModel):
    market_id: str
    telegram_id: Optional[str] = None  # used to look up wallet + open trades
    premium: bool = False


class AdviceResponse(BaseModel):
    market_id: str
    summary: str
    why_trending: str
    risk_factors: list[str]
    suggested_plan: str          # BUY YES | BUY NO | WAIT only
    confidence: float
    disclaimer: str
    tool_calls_used: list[str]
    stale_data_warning: Optional[str] = None


# ── Tool 1: get_market ────────────────────────────────────────────────────────

def get_market(market_id: str) -> dict:
    """
    Reads the Market table and the 5 most recent AISignal rows for this market.
    Gives OpenClaw current odds, price change, volume ratio, and signal history.
    """
    with Session(engine) as session:
        market = session.get(Market, market_id)
        if not market:
            raise HTTPException(
                status_code=404,
                detail=f"Market '{market_id}' not found in cache. Has Intern 1 synced it yet?"
            )

        recent_signals = session.exec(
            select(AISignal)
            .where(AISignal.market_id == market_id)
            .order_by(AISignal.timestamp.desc())
            .limit(5)
        ).all()

        return {
            "id": market.id,
            "question": market.question,
            "category": market.category,
            "current_odds": market.current_odds,
            "previous_odds": market.previous_odds,
            "price_change": round(market.current_odds - market.previous_odds, 4),
            "volume": market.volume,
            "avg_volume": market.avg_volume,
            "volume_ratio": round(market.volume / market.avg_volume, 2) if market.avg_volume > 0 else 0,
            "is_active": market.is_active,
            "expires_at": market.expires_at.isoformat(),
            "recent_signals": [
                {
                    "prediction": s.prediction,
                    "confidence_score": s.confidence_score,
                    "analysis_summary": s.analysis_summary,
                    "timestamp": s.timestamp.isoformat(),
                }
                for s in recent_signals
            ],
        }


# ── Tool 2: get_signals ───────────────────────────────────────────────────────

def get_signals(top: int = 20) -> dict:
    """
    Reads AISignal table, deduplicates to one signal per market (most recent),
    ranks by confidence_score descending, and returns the top N.
    """
    with Session(engine) as session:
        all_signals = session.exec(
            select(AISignal).order_by(AISignal.timestamp.desc())
        ).all()

        # Keep only the most recent signal per market
        seen: dict = {}
        for s in all_signals:
            if s.market_id not in seen:
                seen[s.market_id] = s

        ranked = sorted(seen.values(), key=lambda x: x.confidence_score, reverse=True)[:top]

        results = []
        for s in ranked:
            market = session.get(Market, s.market_id)
            if market:
                results.append({
                    "market_id": s.market_id,
                    "question": market.question,
                    "prediction": s.prediction,
                    "confidence_score": s.confidence_score,
                    "analysis_summary": s.analysis_summary,
                    "current_odds": market.current_odds,
                    "volume": market.volume,
                    "timestamp": s.timestamp.isoformat(),
                })

        return {
            "signals": results,
            "generated_at": datetime.utcnow().isoformat(),
            "count": len(results),
        }


# ── Tool 3: get_wallet_summary ────────────────────────────────────────────────

def get_wallet_summary(telegram_id: str) -> dict:
    """
    Looks up user by telegram_id, returns open positions with live P&L.
    P&L = (current_odds - odds_at_time) * bet_amount for YES bets.
    P&L = (odds_at_time - current_odds) * bet_amount for NO bets.
    """
    with Session(engine) as session:
        user = session.exec(
            select(User).where(User.telegram_id == telegram_id)
        ).first()

        if not user:
            return {
                "found": False,
                "message": "No user found with this Telegram ID. They may not have traded yet.",
            }

        open_trades = session.exec(
            select(Trade)
            .where(Trade.user_id == user.id)
            .where(Trade.status == "Open")
        ).all()

        all_trades = session.exec(
            select(Trade).where(Trade.user_id == user.id)
        ).all()

        positions = []
        total_pnl = 0.0

        for trade in open_trades:
            market = session.get(Market, trade.market_id)
            if market:
                if trade.outcome_selected == "YES":
                    pnl = (market.current_odds - trade.odds_at_time) * trade.bet_amount
                else:
                    pnl = (trade.odds_at_time - market.current_odds) * trade.bet_amount

                total_pnl += pnl
                positions.append({
                    "market_id": trade.market_id,
                    "question": market.question,
                    "outcome_selected": trade.outcome_selected,
                    "bet_amount": trade.bet_amount,
                    "odds_at_time": trade.odds_at_time,
                    "current_odds": market.current_odds,
                    "unrealised_pnl": round(pnl, 2),
                    "status": trade.status,
                    "placed_at": trade.timestamp.isoformat(),
                })

        return {
            "found": True,
            "username": user.username,
            "wallet_address": user.wallet_address,
            "open_positions": positions,
            "total_unrealised_pnl": round(total_pnl, 2),
            "total_trades": len(all_trades),
            "open_trades": len(open_trades),
        }


# ── Call OpenClaw Gateway ─────────────────────────────────────────────────────

import subprocess

async def call_openclaw(system_prompt: str, user_prompt: str) -> str:
    full_message = f"{system_prompt}\n\n{user_prompt}"
    
    try:
        result = subprocess.run(
            [
                "openclaw", "agent",
                "--message", full_message,
                "--json"
            ],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode != 0:
            raise HTTPException(
                status_code=503,
                detail=f"OpenClaw error: {result.stderr}"
            )
        
        data = json.loads(result.stdout)
        return data.get("text", data.get("response", ""))
        
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=503, detail="OpenClaw timed out.")
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="openclaw CLI not found. Is it installed?")



# ── Parse LLM Response ────────────────────────────────────────────────────────

def parse_response(raw: str, market_id: str, tools_called: list[str]) -> AdviceResponse:
    """
    Strips markdown fences if present, parses JSON, enforces business rules.
    Returns a safe fallback if the LLM response can't be parsed.
    """
    cleaned = raw.strip()

    # Strip ```json ... ``` if LLM wrapped its response
    if cleaned.startswith("```"):
        parts = cleaned.split("```")
        cleaned = parts[1] if len(parts) > 1 else cleaned
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return AdviceResponse(
            market_id=market_id,
            summary="Agent response could not be parsed. Please try again.",
            why_trending="Unknown",
            risk_factors=["Response parsing failed"],
            suggested_plan="WAIT",
            confidence=0.0,
            disclaimer="This is not financial advice. Paper trading only.",
            tool_calls_used=tools_called,
        )

    # Enforce suggested_plan — only 3 allowed values
    valid_plans = {"BUY YES", "BUY NO", "WAIT"}
    suggested = str(data.get("suggested_plan", "WAIT")).upper().strip()
    if suggested not in valid_plans:
        suggested = "WAIT"

    return AdviceResponse(
        market_id=data.get("market_id", market_id),
        summary=data.get("summary", ""),
        why_trending=data.get("why_trending", ""),
        risk_factors=data.get("risk_factors", []),
        suggested_plan=suggested,
        confidence=float(data.get("confidence", 0.5)),
        disclaimer="This is not financial advice. Paper trading only.",
        tool_calls_used=tools_called,
        stale_data_warning=data.get("stale_data_warning"),
    )


# ── Main Endpoint ─────────────────────────────────────────────────────────────

@router.post("/advice", response_model=AdviceResponse)
async def get_advice(request: AdviceRequest):
    """
    The ONLY endpoint that activates OpenClaw.
    Collects context from 3 tools, builds a prompt, sends to OpenClaw/LLM.
    Never writes to the database. Never executes trades.
    """
    tools_called = []

    # Tool 1 — market data
    try:
        market_data = get_market(request.market_id)
        tools_called.append("get_market")
    except HTTPException:
        raise

    # Tool 2 — signals
    signals_data = get_signals()
    tools_called.append("get_signals")

    # Tool 3 — wallet (optional, only if telegram_id provided)
    wallet_context = ""
    if request.telegram_id:
        wallet_data = get_wallet_summary(request.telegram_id)
        tools_called.append("get_wallet_summary")
        wallet_context = f"\nUser wallet context:\n{json.dumps(wallet_data, indent=2)}"

    # Build full data context to inject into the prompt
    data_context = f"""
Market Data:
{json.dumps(market_data, indent=2)}

Current Top Signals:
{json.dumps(signals_data, indent=2)}
{wallet_context}
"""

    # Choose prompt based on premium flag
    template = PREMIUM_ADVICE_USER_PROMPT if request.premium else ADVICE_USER_PROMPT
    user_prompt = template.format(
        market_id=request.market_id,
        wallet_context=wallet_context,
    ) + f"\n\n--- FETCHED DATA ---\n{data_context}"

    # Send to OpenClaw
    raw_response = await call_openclaw(ADVICE_SYSTEM_PROMPT, user_prompt)

    return parse_response(raw_response, request.market_id, tools_called)