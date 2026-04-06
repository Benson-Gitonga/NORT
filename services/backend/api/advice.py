import json
import httpx
import os
import asyncio
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
from tavily import TavilyClient
from dotenv import load_dotenv
from sqlmodel import Session, select

load_dotenv()

from services.agent.prompt_templates import ADVICE_SYSTEM_PROMPT
from services.backend.core.x402_verifier import has_premium_access, payment_required_payload
from services.backend.data.database import engine
from services.backend.data.models import Market, AISignal
from services.backend.api.auth import get_current_user

router = APIRouter(prefix="/agent", tags=["Agent"])

OPENCLAW_URL   = os.getenv("OPENCLAW_URL", "https://openrouter.ai/api/v1/chat/completions")
OPENCLAW_TOKEN = os.getenv("OPENCLAW_TOKEN", "").strip()
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "").strip()

# ─────────────────────────────────────────────────────────────
# Request / Response Models
# ─────────────────────────────────────────────────────────────

class AdviceRequest(BaseModel):
    market_id: str
    telegram_id: Optional[str] = None
    premium: bool = False

class AdviceResponse(BaseModel):
    market_id: str
    summary: str
    why_trending: str
    risk_factors: list[str]
    suggested_plan: str
    confidence: float
    disclaimer: str
    tool_calls_used: list[str]
    stale_data_warning: Optional[str] = None

# ─────────────────────────────────────────────────────────────
# Tavily Search
# ─────────────────────────────────────────────────────────────

def tavily_search(query: str, max_results: int = 5) -> str:
    try:
        client = TavilyClient(api_key=TAVILY_API_KEY)
        response = client.search(query, max_results=max_results)
        results = response.get("results", [])
        if not results:
            return "No results found."
        return "\n".join([f"- {r['title']}: {r['content']}" for r in results])
    except Exception as e:
        print(f"[Tavily Error] {e}")
        return "Search unavailable."

# ─────────────────────────────────────────────────────────────
# Search Pre-Fetch — 3 parallel Tavily searches
# ─────────────────────────────────────────────────────────────

async def search_prefetch(market_question: str) -> dict:
    loop = asyncio.get_event_loop()

    news_query    = f'"{market_question}" odds OR prediction OR analyst 2026'
    social_query  = f'"{market_question}" reddit OR twitter OR sentiment OR community opinion'
    context_query = f'"{market_question}" explained OR background OR history OR resolution'

    print(f"[Search] News:    {news_query}")
    print(f"[Search] Social:  {social_query}")
    print(f"[Search] Context: {context_query}")

    news_task    = loop.run_in_executor(None, tavily_search, news_query,    6)
    social_task  = loop.run_in_executor(None, tavily_search, social_query,  5)
    context_task = loop.run_in_executor(None, tavily_search, context_query, 4)

    try:
        news_results, social_results, context_results = await asyncio.wait_for(
            asyncio.gather(news_task, social_task, context_task),
            timeout=15.0
        )
    except asyncio.TimeoutError:
        print("[Search] Pre-fetch timed out — continuing with empty context")
        news_results    = "Search timed out."
        social_results  = "Search timed out."
        context_results = "Search timed out."

    print(f"[Search] News results:\n{news_results}")
    print(f"[Search] Social results:\n{social_results}")
    print(f"[Search] Context results:\n{context_results}")

    return {
        "news":    news_results,
        "social":  social_results,
        "context": context_results,
        "queries": {
            "news":    news_query,
            "social":  social_query,
            "context": context_query
        }
    }

# ─────────────────────────────────────────────────────────────
# OpenClaw Caller — single-shot enriched prompt
# ─────────────────────────────────────────────────────────────

async def call_openclaw(
    market_id: str,
    market_question: str,
    market_data: dict,
    market_signal: dict,
    search_context: dict
) -> str:
    if not OPENCLAW_TOKEN:
        raise HTTPException(status_code=503, detail="Missing OPENCLAW_TOKEN in .env")

    user_message = f"""/advice {market_id}

MARKET QUESTION: {market_question}

━━━ MARKET DATA (Neon) ━━━
{json.dumps(market_data, indent=2)}

━━━ AI SIGNAL FOR THIS MARKET ━━━
{json.dumps(market_signal, indent=2) if market_signal else "No signal data available."}

━━━ RECENT NEWS ━━━
{search_context['news']}

━━━ SOCIAL BUZZ & SENTIMENT (Reddit / Twitter) ━━━
{search_context['social']}

━━━ BACKGROUND & CONTEXT ━━━
{search_context['context']}

━━━ YOUR TASK ━━━
Using ALL the data above — market data, AI signal, news, social sentiment,
and background context — provide a comprehensive analysis of this prediction market.
Reference specific data points from the news and social sections in your analysis.
Return JSON only. The market_id field must be exactly: {market_id}
"""

    payload = {
        "model": "anthropic/claude-3-haiku",
        "messages": [
            {"role": "system", "content": ADVICE_SYSTEM_PROMPT},
            {"role": "user",   "content": user_message}
        ]
    }

    print(f"[OpenClaw] Sending prompt for market {market_id}")

    async with httpx.AsyncClient(timeout=120) as client:
        try:
            response = await client.post(
                OPENCLAW_URL,
                json=payload,
                headers={
                    "Authorization": f"Bearer {OPENCLAW_TOKEN}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://nort.onrender.com",
                    "X-Title": "Nort Advisor"
                }
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="OpenClaw gateway unreachable")
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=503, detail=f"OpenClaw error {e.response.status_code}")

# ─────────────────────────────────────────────────────────────
# Debug Endpoint
# ─────────────────────────────────────────────────────────────

@router.get("/advice/debug")
async def debug_openclaw():
    market_question = "Will MicroStrategy sell any Bitcoin in 2025?"
    search_context = await search_prefetch(market_question)
    raw = await call_openclaw(
        market_id="debug",
        market_question=market_question,
        market_data={"debug": True},
        market_signal={},
        search_context=search_context
    )
    return {"raw": raw, "search_context": search_context}

# ─────────────────────────────────────────────────────────────
# LLM Response Parser
# ─────────────────────────────────────────────────────────────

def parse_response(raw: str, market_id: str, tool_calls_used: list[str]) -> AdviceResponse:
    cleaned = raw.strip()

    if cleaned.startswith("```"):
        parts = cleaned.split("```")
        cleaned = parts[1] if len(parts) > 1 else cleaned
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()

    start = cleaned.find("{")
    end = cleaned.rfind("}") + 1
    if start != -1 and end > start:
        cleaned = cleaned[start:end]

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return AdviceResponse(
            market_id=market_id,
            summary="Agent response could not be parsed.",
            why_trending="Unknown",
            risk_factors=["Invalid AI response"],
            suggested_plan="WAIT",
            confidence=0.0,
            disclaimer="This is not financial advice. Paper trading only.",
            tool_calls_used=tool_calls_used or ["parse_failed"]
        )

    valid_plans = {"BUY YES", "BUY NO", "WAIT"}
    suggested = str(data.get("suggested_plan", "WAIT")).upper().strip()
    if suggested not in valid_plans:
        suggested = "WAIT"

    return AdviceResponse(
        market_id=market_id,
        summary=data.get("summary", ""),
        why_trending=data.get("why_trending", ""),
        risk_factors=data.get("risk_factors", []),
        suggested_plan=suggested,
        confidence=float(data.get("confidence", 0.5)),
        disclaimer="This is not financial advice. Paper trading only.",
        tool_calls_used=tool_calls_used,
        stale_data_warning=data.get("stale_data_warning")
    )

# ─────────────────────────────────────────────────────────────
# Data Fetchers — read directly from Neon via SQLModel
#
# Previously these called localhost:8000 which doesn't exist
# on Render. Now they query the database directly using the
# same engine that the rest of the app uses.
# ─────────────────────────────────────────────────────────────

def fetch_market_data(market_id: str) -> dict:
    """
    Fetch a single market record directly from Neon by ID.
    Returns a plain dict for JSON serialization.
    """
    try:
        with Session(engine) as session:
            market = session.get(Market, market_id)
            if not market:
                print(f"[Market] ID {market_id} not found in Neon")
                return {}
            return {
                "id":             market.id,
                "question":       market.question,
                "category":       market.category,
                "current_odds":   market.current_odds,
                "previous_odds":  market.previous_odds,
                "volume":         market.volume,
                "avg_volume":     market.avg_volume,
                "is_active":      market.is_active,
                "expires_at":     str(market.expires_at) if market.expires_at else None,
            }
    except Exception as e:
        import traceback
        print(f"[Market] Neon fetch failed: {e}\n{traceback.format_exc()}")
        return {}


def fetch_market_signal(market_id: str) -> dict:
    """
    Fetch the AI signal for a specific market directly from Neon.
    Returns the most recent signal record or an empty dict.
    """
    try:
        with Session(engine) as session:
            statement = (
                select(AISignal)
                .where(AISignal.market_id == market_id)
                .order_by(AISignal.timestamp.desc())
                .limit(1)
            )
            signal = session.exec(statement).first()
            if not signal:
                print(f"[Signal] No signal found for market {market_id}")
                return {}
            return {
                "market_id":        signal.market_id,
                "prediction":       signal.prediction,
                "confidence_score": signal.confidence_score,
                "analysis_summary": signal.analysis_summary,
                "timestamp":        str(signal.timestamp) if signal.timestamp else None,
            }
    except Exception as e:
        import traceback
        print(f"[Signal] Neon fetch failed: {e}\n{traceback.format_exc()}")
        return {}

# ─────────────────────────────────────────────────────────────
# MAIN ENDPOINT
#
# Flow:
#   1. Fetch market data + AI signal directly from Neon
#   2. Run 3 Tavily searches in parallel (news + social + context)
#   3. Bundle everything into one enriched prompt
#   4. Send to OpenClaw → single-shot analysis
#   5. Parse → return AdviceResponse
# ─────────────────────────────────────────────────────────────

@router.post("/advice", response_model=AdviceResponse)
@router.post("/advice")
async def get_advice(request: Request, body_req: AdviceRequest, current_user: dict = Depends(get_current_user)):
    from services.backend.main import limiter
    
    # We must call the limiter check manually if we can't use the decorator smoothly with request unpacking
    # But usually `@limiter.limit("5/minute")` is applied before the function. Let's just wrap it.
    pass

@router.post("/advice", response_model=AdviceResponse)
async def get_advice(
    request: Request, 
    body_req: AdviceRequest, 
    current_user: dict = Depends(get_current_user)
):
    from services.backend.main import limiter
    
    tool_calls_used: list[str] = []

    if body_req.premium and not has_premium_access(current_user["wallet"], body_req.market_id):
        return JSONResponse(
            status_code=402,
            content=payment_required_payload(body_req.market_id),
        )

    # 1. Fetch directly from Neon — no localhost calls
    market_data   = fetch_market_data(body_req.market_id)
    market_signal = fetch_market_signal(body_req.market_id)

    # 2. Extract market question
    market_question = (
        market_data.get("question") or
        market_data.get("summary") or
        f"prediction market {body_req.market_id}"
    ).strip()

    print(f"[Agent] Market {body_req.market_id}: {market_question}")

    # 3. Run 3 Tavily searches in parallel
    search_context = await search_prefetch(market_question)
    tool_calls_used += [
        f"tavily_news: {search_context['queries']['news']}",
        f"tavily_social: {search_context['queries']['social']}",
        f"tavily_context: {search_context['queries']['context']}"
    ]

    # 4. Send everything to OpenClaw in one enriched prompt
    raw_response = await call_openclaw(
        market_id=body_req.market_id,
        market_question=market_question,
        market_data=market_data,
        market_signal=market_signal,
        search_context=search_context
    )

    print(f"[Agent] Raw response: {raw_response}")
    return parse_response(raw_response, body_req.market_id, tool_calls_used)
