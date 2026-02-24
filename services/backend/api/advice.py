import json
import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from ddgs import DDGS

# Prompt
from services.agent.prompt_templates import ADVICE_SYSTEM_PROMPT, build_advice_user_prompt

router = APIRouter(prefix="/agent", tags=["Agent"])

# OpenClaw gateway
OPENCLAW_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENCLAW_TOKEN = "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"

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
# Web Search (DuckDuckGo)
# ─────────────────────────────────────────────────────────────

def build_search_query(question: str) -> str:
    stopwords = {
        "will", "does", "is", "are", "the", "a", "an", "in", "of",
        "by", "to", "than", "less", "more", "going", "be", "have",
        "for", "this", "that", "with", "from", "and", "or", "not"
    }
    words = question.replace("?", "").replace(",", "").split()
    keywords = [w for w in words if w.lower() not in stopwords and len(w) > 2]
    return " ".join(keywords[:6])


def fetch_news(query: str, max_results: int = 5) -> str:
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        if not results:
            return "No recent news found."
        snippets = [f"- {r['title']}: {r['body']}" for r in results]
        return "\n".join(snippets)
    except Exception as e:
        print(f"[DDG Search Error] {e}")
        return "Web search unavailable."


# ─────────────────────────────────────────────────────────────
# OpenClaw Caller
# ─────────────────────────────────────────────────────────────

async def call_openclaw(system_prompt: str, user_prompt: str) -> str:
    payload = {
        "model": "anthropic/claude-3-haiku",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    }

    async with httpx.AsyncClient(timeout=120) as client:
        try:
            response = await client.post(
                OPENCLAW_URL,
                json=payload,
                headers={
                    "Authorization": f"Bearer {OPENCLAW_TOKEN}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "http://localhost:8000",
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


@router.get("/advice/debug")
async def debug_openclaw():
    raw = await call_openclaw(
        ADVICE_SYSTEM_PROMPT,
        "Analyze market 517310. Return JSON only."
    )
    return {"raw": raw}


# ─────────────────────────────────────────────────────────────
# LLM Response Parser (Safety Layer)
# ─────────────────────────────────────────────────────────────

def parse_response(raw: str, market_id: str) -> AdviceResponse:
    cleaned = raw.strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}") + 1
    if start != -1 and end > start:
        cleaned = cleaned[start:end]

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
            summary="Agent response could not be parsed.",
            why_trending="Unknown",
            risk_factors=["Invalid AI response"],
            suggested_plan="WAIT",
            confidence=0.0,
            disclaimer="This is not financial advice. Paper trading only.",
            tool_calls_used=["parse_failed"]
        )

    valid_plans = {"BUY YES", "BUY NO", "WAIT"}
    suggested = str(data.get("suggested_plan", "WAIT")).upper().strip()
    if suggested not in valid_plans:
        suggested = "WAIT"

    return AdviceResponse(
        market_id=market_id,  # Always use the real market_id, never trust LLM for this
        summary=data.get("summary", ""),
        why_trending=data.get("why_trending", ""),
        risk_factors=data.get("risk_factors", []),
        suggested_plan=suggested,
        confidence=float(data.get("confidence", 0.5)),
        disclaimer="This is not financial advice. Paper trading only.",
        tool_calls_used=["openclaw_agent", "duckduckgo_search"],
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
            else:
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
    """Pull only the signal entry matching this market, if it exists."""
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
# ─────────────────────────────────────────────────────────────

@router.post("/advice", response_model=AdviceResponse)
async def get_advice(request: AdviceRequest):
    # 1. Fetch market data and signals
    market_data = await fetch_market_data(request.market_id)
    signals_data = await fetch_signals()

    # 2. Extract only the signal for this specific market
    market_signal = extract_market_signal(signals_data, request.market_id)

    # 3. Build focused search query
    market_question = market_data.get("question", f"prediction market {request.market_id}")
    search_query = build_search_query(market_question)
    print(f"[DDG] Market question: {market_question}")
    print(f"[DDG] Search query:    {search_query}")

    # 4. Fetch news
    news_snippets = fetch_news(search_query, max_results=5)
    print(f"[DDG] Results:\n{news_snippets}")

    # 5. Build tightly focused prompt — one market only
    user_message = f"""
You are analyzing ONE specific prediction market. Focus only on this market.

MARKET ID: {request.market_id}
MARKET QUESTION: {market_question}

MARKET DATA:
{json.dumps(market_data, indent=2)}

SIGNAL FOR THIS MARKET:
{json.dumps(market_signal, indent=2) if market_signal else "No signal data available."}

RECENT NEWS (searched: "{search_query}"):
{news_snippets}

Return JSON only. The market_id field must be exactly: {request.market_id}
"""

    raw_response = await call_openclaw(ADVICE_SYSTEM_PROMPT, user_message)
    print(f"RAW RESPONSE: {raw_response}")
    return parse_response(raw_response, request.market_id)

@router.get("/markets")
async def get_markets_mock():
    return {
        "markets": [
            {"id": "521947", "question": "Will Trump deport <250k?", "yes_price": 0.35, "no_price": 0.65, "volume": 125000},
            {"id": "549869", "question": "Bitcoin $100k by June?", "yes_price": 0.68, "no_price": 0.32, "volume": 89000}
        ],
        "count": 2,
        "cached_at": "2026-02-24T22:00:00Z"
    }
