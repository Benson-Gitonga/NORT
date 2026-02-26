import json
import httpx
import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

from services.agent.prompt_templates import ADVICE_SYSTEM_PROMPT

router = APIRouter(prefix="/agent", tags=["Agent"])

OPENCLAW_URL = os.getenv("OPENCLAW_URL", "https://openrouter.ai/api/v1/chat/completions")
OPENCLAW_TOKEN = os.getenv("OPENCLAW_TOKEN", "").strip()

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
# OpenClaw Caller
# Simple single-shot call to OpenClaw/OpenRouter.
# No tool loop, no DDG — just sends the prompt and returns
# the raw response for parsing.
# ─────────────────────────────────────────────────────────────

async def call_openclaw(system_prompt: str, user_prompt: str) -> str:
    """Send a prompt to OpenClaw and return the raw text response."""
    if not OPENCLAW_TOKEN:
        raise HTTPException(status_code=503, detail="Missing OPENCLAW_TOKEN in .env")

    payload = {
        "model": "anthropic/claude-3-haiku",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt}
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

# ─────────────────────────────────────────────────────────────
# Debug Endpoint
# ─────────────────────────────────────────────────────────────

@router.get("/advice/debug")
async def debug_openclaw():
    """Fire a raw call to verify OpenClaw is reachable and responding."""
    raw = await call_openclaw(
        ADVICE_SYSTEM_PROMPT,
        "Analyze market 517310. Return JSON only."
    )
    return {"raw": raw}

# ─────────────────────────────────────────────────────────────
# LLM Response Parser (Safety Layer)
# Strips markdown fences, extracts JSON, maps to AdviceResponse.
# Falls back gracefully if parsing fails — never crashes.
# ─────────────────────────────────────────────────────────────

def parse_response(raw: str, market_id: str) -> AdviceResponse:
    """Parse raw LLM output into a validated AdviceResponse."""
    cleaned = raw.strip()

    # Strip markdown code fences if present (```json ... ```)
    if cleaned.startswith("```"):
        parts = cleaned.split("```")
        cleaned = parts[1] if len(parts) > 1 else cleaned
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()

    # Extract the JSON object even if there's surrounding text
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
            tool_calls_used=["parse_failed"]
        )

    # Validate suggested_plan — only allow known values
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
        tool_calls_used=["openclaw_agent"],
        stale_data_warning=data.get("stale_data_warning")
    )

# ─────────────────────────────────────────────────────────────
# Data Fetchers
# ─────────────────────────────────────────────────────────────

async def fetch_market_data(market_id: str) -> dict:
    """Fetch market record from the local /markets/ endpoint."""
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
    """Fetch top AI signals from the local /signals/ endpoint."""
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
    """Find the AI signal record matching this market_id."""
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
# Simple flow:
#   1. Fetch SQLite baseline (market data + AI signal)
#   2. Build prompt with all available context
#   3. Send to OpenClaw → get JSON response
#   4. Parse and return AdviceResponse
# ─────────────────────────────────────────────────────────────

@router.post("/advice", response_model=AdviceResponse)
async def get_advice(request: AdviceRequest):

    # 1. Fetch baseline data from SQLite
    market_data  = await fetch_market_data(request.market_id)
    signals_data = await fetch_signals()

    # 2. Find and merge the AI signal for this market
    market_signal = extract_market_signal(signals_data, request.market_id)

    # 3. Extract the market question
    market_question = (
        market_data.get("question") or
        market_data.get("summary") or
        f"prediction market {request.market_id}"
    ).strip()

    print(f"[Agent] Market {request.market_id}: {market_question}")

    # 4. Build the prompt
    user_message = f"""
You are analyzing ONE specific prediction market. Focus only on this market.

MARKET ID: {request.market_id}
MARKET QUESTION: {market_question}

MARKET DATA:
{json.dumps(market_data, indent=2)}

SIGNAL FOR THIS MARKET:
{json.dumps(market_signal, indent=2) if market_signal else "No signal data available."}

Return JSON only. The market_id field must be exactly: {request.market_id}
"""

    # 5. Send to OpenClaw and parse response
    raw_response = await call_openclaw(ADVICE_SYSTEM_PROMPT, user_message)
    print(f"RAW RESPONSE: {raw_response}")
    return parse_response(raw_response, request.market_id)