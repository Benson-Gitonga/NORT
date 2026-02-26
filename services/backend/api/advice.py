import json
import httpx
import os
import asyncio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from tavily import TavilyClient
from dotenv import load_dotenv

load_dotenv()

from services.agent.prompt_templates import ADVICE_SYSTEM_PROMPT

router = APIRouter(prefix="/agent", tags=["Agent"])

OPENCLAW_URL  = os.getenv("OPENCLAW_URL", "https://openrouter.ai/api/v1/chat/completions")
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
#
# Proper search API — no scraping, no hanging, works from Render.
# Free tier: 1,000 queries/month.
# Replaces DuckDuckGo which was hanging due to bot detection.
# ─────────────────────────────────────────────────────────────

def tavily_search(query: str, max_results: int = 5) -> str:
    """
    Run a Tavily search and return formatted snippets.
    Returns a fallback string on any failure — never crashes.
    """
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
# Search Pre-Fetch
#
# Fires 3 Tavily searches in parallel BEFORE calling OpenClaw:
#   1. News    — recent articles, odds, analyst takes
#   2. Social  — Reddit/Twitter sentiment and buzz
#   3. Context — background, resolution criteria, history
#
# All three run concurrently via asyncio.gather so total time
# = slowest single query, not all three combined.
#
# Results are injected directly into the OpenClaw prompt so
# the model has real-world context before it starts analyzing.
# ─────────────────────────────────────────────────────────────

async def search_prefetch(market_question: str) -> dict:
    """
    Fires 3 Tavily searches in parallel and returns all results.
    Hard capped at 15 seconds total via asyncio.wait_for.
    """
    loop = asyncio.get_event_loop()

    # Build the three targeted query strings
    news_query    = f'"{market_question}" odds OR prediction OR analyst 2026'
    social_query  = f'"{market_question}" reddit OR twitter OR sentiment OR community opinion'
    context_query = f'"{market_question}" explained OR background OR history OR resolution'

    print(f"[Search] News:    {news_query}")
    print(f"[Search] Social:  {social_query}")
    print(f"[Search] Context: {context_query}")

    # Run all three concurrently in thread executor
    # (Tavily is blocking I/O — run_in_executor keeps FastAPI event loop free)
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
# OpenClaw Caller
#
# Single-shot call — no tool loop.
# OpenClaw receives everything in one enriched prompt:
#   - Market data + AI signal from SQLite
#   - Tavily news results
#   - Tavily social/sentiment results
#   - Tavily background/context results
# It just needs to analyze and return JSON.
# ─────────────────────────────────────────────────────────────

async def call_openclaw(
    market_id: str,
    market_question: str,
    market_data: dict,
    market_signal: dict,
    search_context: dict
) -> str:
    """
    Sends one enriched prompt to OpenClaw containing all available context.
    Returns the raw text response for parsing.
    """
    if not OPENCLAW_TOKEN:
        raise HTTPException(status_code=503, detail="Missing OPENCLAW_TOKEN in .env")

    user_message = f"""/advice {market_id}

MARKET QUESTION: {market_question}

━━━ MARKET DATA (SQLite) ━━━
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
    """Fire a full pipeline test with a real question."""
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
# LLM Response Parser (Safety Layer)
# ─────────────────────────────────────────────────────────────

def parse_response(raw: str, market_id: str, tool_calls_used: list[str]) -> AdviceResponse:
    """Parse raw LLM output into a validated AdviceResponse."""
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
# Data Fetchers
# ─────────────────────────────────────────────────────────────

async def fetch_market_data(market_id: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"http://localhost:8000/markets/{market_id}")
            if response.status_code == 200:
                return response.json()
            print(f"[Market] Status {response.status_code}")
    except Exception as e:
        import traceback
        print(f"[Market] Fetch failed: {e}\n{traceback.format_exc()}")
    return {}

async def fetch_signals() -> dict:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get("http://localhost:8000/signals/?top=20")
            if response.status_code == 200:
                return response.json()
    except Exception as e:
        import traceback
        print(f"[Signals] Fetch failed: {e}\n{traceback.format_exc()}")
    return {}

def extract_market_signal(signals_data: dict, market_id: str) -> dict:
    try:
        items = signals_data if isinstance(signals_data, list) else signals_data.get("signals", [])
        for item in items:
            if str(item.get("id")) == str(market_id) or str(item.get("market_id")) == str(market_id):
                return item
    except Exception:
        pass
    return {}

# ─────────────────────────────────────────────────────────────
# MAIN ENDPOINT
#
# Flow:
#   1. Fetch SQLite baseline (market data + AI signal)
#   2. Run 3 Tavily searches in parallel (news + social + context)
#   3. Bundle everything into one enriched prompt
#   4. Send to OpenClaw → single-shot analysis
#   5. Parse → return AdviceResponse
# ─────────────────────────────────────────────────────────────

@router.post("/advice", response_model=AdviceResponse)
async def get_advice(request: AdviceRequest):
    tool_calls_used: list[str] = []

    # 1. Fetch SQLite baseline
    market_data  = await fetch_market_data(request.market_id)
    signals_data = await fetch_signals()
    market_signal = extract_market_signal(signals_data, request.market_id)

    # 2. Extract market question
    market_question = (
        market_data.get("question") or
        market_data.get("summary") or
        f"prediction market {request.market_id}"
    ).strip()

    print(f"[Agent] Market {request.market_id}: {market_question}")

    # 3. Run 3 Tavily searches in parallel
    search_context = await search_prefetch(market_question)
    tool_calls_used += [
        f"tavily_news: {search_context['queries']['news']}",
        f"tavily_social: {search_context['queries']['social']}",
        f"tavily_context: {search_context['queries']['context']}"
    ]

    # 4. Send everything to OpenClaw in one enriched prompt
    raw_response = await call_openclaw(
        market_id=request.market_id,
        market_question=market_question,
        market_data=market_data,
        market_signal=market_signal,
        search_context=search_context
    )

    print(f"[Agent] Raw response: {raw_response}")
    return parse_response(raw_response, request.market_id, tool_calls_used)