import json
import httpx
import os
import asyncio
import time
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
from tavily import TavilyClient
from dotenv import load_dotenv
from sqlmodel import Session, select
from deep_translator import GoogleTranslator

load_dotenv()

from services.agent.orchestrator import run_orchestrator
from services.agent.prompt_templates import ADVICE_SYSTEM_PROMPT
from services.agent.policies import check_policy
from services.agent.executor import AutoTradeEngine
from services.backend.core.x402_verifier import has_premium_access, payment_required_payload
from services.backend.data.database import engine
from services.backend.data.models import Market, AISignal, AuditLog, Conversation

router = APIRouter(prefix="/agent", tags=["Agent"])

OPENROUTER_URL = os.getenv("OPENROUTER_URL", "https://openrouter.ai/api/v1/chat/completions")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "").strip()

# ─────────────────────────────────────────────────────────────
# Request / Response Models
# ─────────────────────────────────────────────────────────────

class AdviceRequest(BaseModel):
    market_id: str
    telegram_id: Optional[str] = None
    premium: bool = False
    language: str = "en"

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
    auto_trade_result: Optional[dict] = None   # populated if AutoTradeEngine ran

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
    if not OPENROUTER_API_KEY:
        raise HTTPException(status_code=503, detail="Missing OPENROUTER_API_KEY in .env")

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
        "model": "meta-llama/llama-3.3-70b-instruct:free",
        "messages": [
            {"role": "system", "content": ADVICE_SYSTEM_PROMPT},
            {"role": "user",   "content": user_message}
        ]
    }

    print(f"[OpenClaw] Sending prompt for market {market_id}")

    async with httpx.AsyncClient(timeout=120) as client:
        try:
            response = await client.post(
                OPENROUTER_URL,
                json=payload,
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
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
async def debug_openrouter():
    market_question = "Will MicroStrategy sell any Bitcoin in 2025?"
    search_context = await search_prefetch(market_question)
    raw = await run_orchestrator(
        market_id="debug",
        market_data={"question": market_question},
        market_signal={},
        search_context=search_context
    )
    return {"raw": raw, "search_context": search_context}

# ─────────────────────────────────────────────────────────────
# LLM Response Parser
# ─────────────────────────────────────────────────────────────

def parse_response(
    raw: str,
    market_id: str,
    tool_calls_used: list[str],
    technical_momentum: str = "NEUTRAL",
    sentiment_label: str = "Neutral",
) -> AdviceResponse:
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

    confidence = float(data.get("confidence", 0.5))

    # Task 8B: Python confidence cap — AI cannot override this
    # If Technical momentum and Sentiment disagree, cap at 0.70
    tech_bullish  = technical_momentum == "BULLISH"
    tech_bearish  = technical_momentum == "BEARISH"
    sent_bullish  = sentiment_label == "Bullish"
    sent_bearish  = sentiment_label == "Bearish"
    agents_disagree = (tech_bullish and sent_bearish) or (tech_bearish and sent_bullish)
    if agents_disagree and confidence > 0.70:
        print(f"[ConfidenceCap] Technical={technical_momentum} vs Sentiment={sentiment_label} — capping {confidence:.2f} → 0.70")
        confidence = 0.70

    return AdviceResponse(
        market_id=market_id,
        summary=data.get("summary", ""),
        why_trending=data.get("why_trending", ""),
        risk_factors=data.get("risk_factors", []),
        suggested_plan=suggested,
        confidence=confidence,
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
# Rate Limit Helper  (Task 3)
# Max 5 advice calls per user per hour, checked against AuditLog
# ─────────────────────────────────────────────────────────────

RATE_LIMIT_MAX   = 5     # calls per window
RATE_LIMIT_HOURS = 1     # window size in hours

def check_rate_limit(telegram_id: str) -> None:
    """
    Raises HTTP 429 if this user has made >= 5 advice calls in the last hour.
    Called before any expensive work (Tavily + LLM) so we never burn credits.
    No-ops for anonymous users (telegram_id is None) to avoid blocking free debug calls.
    """
    if not telegram_id:
        return
    window_start = datetime.now(timezone.utc) - timedelta(hours=RATE_LIMIT_HOURS)
    with Session(engine) as session:
        count = session.exec(
            select(AuditLog)
            .where(AuditLog.telegram_user_id == telegram_id)
            .where(AuditLog.action == "advice")
            .where(AuditLog.created_at >= window_start)
        ).all()
    if len(count) >= RATE_LIMIT_MAX:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded: max {RATE_LIMIT_MAX} advice calls per hour. Try again later."
        )


def write_audit_log(
    telegram_id: Optional[str],
    market_id: Optional[str],
    premium: bool,
    success: bool,
    response_time_ms: Optional[int],
    action: str = "advice",
) -> None:
    """Writes a single row to audit_logs. Never raises — errors are swallowed."""
    try:
        with Session(engine) as session:
            log = AuditLog(
                telegram_user_id=telegram_id,
                action=action,
                market_id=market_id,
                premium=premium,
                success=success,
                response_time_ms=response_time_ms,
            )
            session.add(log)
            session.commit()
    except Exception as e:
        print(f"[AuditLog] Write failed (non-fatal): {e}")


# ─────────────────────────────────────────────────────────────
# Task 5A — Advice Cache
# Returns a cached AdviceResponse if the same user+market was advised
# within the last 30 minutes, skipping the full LLM pipeline.
# ─────────────────────────────────────────────────────────────

CACHE_WINDOW_MINUTES = 30

def get_cached_advice(telegram_id: Optional[str], market_id: str) -> Optional[AdviceResponse]:
    """
    Looks up the most recent Conversation record for this user+market.
    If the last assistant message was within 30 minutes and contains valid
    advice JSON, deserialises and returns it with a staleness warning.
    Returns None if no valid cache entry exists.
    """
    if not telegram_id:
        return None
    try:
        window_start = datetime.now(timezone.utc) - timedelta(minutes=CACHE_WINDOW_MINUTES)
        with Session(engine) as session:
            conv = session.exec(
                select(Conversation)
                .where(Conversation.telegram_user_id == telegram_id)
                .where(Conversation.market_id == market_id)
                .order_by(Conversation.updated_at.desc())
            ).first()
            if not conv or not conv.messages:
                return None
            # Find the latest assistant message
            assistant_msgs = [m for m in conv.messages if m.get("role") == "assistant"]
            if not assistant_msgs:
                return None
            last = assistant_msgs[-1]
            ts_str = last.get("ts")
            if not ts_str:
                return None
            ts = datetime.fromisoformat(ts_str)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts < window_start:
                return None  # Cache expired
            # Parse the cached advice payload
            payload = last.get("advice")
            if not payload or not isinstance(payload, dict):
                return None
            cached = AdviceResponse(**payload)
            age_mins = int((datetime.now(timezone.utc) - ts).total_seconds() / 60)
            cached.stale_data_warning = (
                f"Cached advice from {age_mins} minute(s) ago. "
                f"Full analysis skipped to save resources."
            )
            print(f"[Cache] HIT for user={telegram_id} market={market_id} age={age_mins}m")
            return cached
    except Exception as e:
        print(f"[Cache] Read error (non-fatal): {e}")
        return None


# ─────────────────────────────────────────────────────────────
# Task 5B — Conversation History Helpers
# Load the last 10 messages (5 exchanges) for a user+market and
# save the latest advice turn back to the Conversation table.
# ─────────────────────────────────────────────────────────────

def load_conversation_history(telegram_id: Optional[str], market_id: str) -> list:
    """
    Returns the last 10 messages for this user+market as a list of
    {role, content} dicts — the format run_synthesis() already expects.
    Returns [] if no history exists or on any error.
    """
    if not telegram_id:
        return []
    try:
        with Session(engine) as session:
            conv = session.exec(
                select(Conversation)
                .where(Conversation.telegram_user_id == telegram_id)
                .where(Conversation.market_id == market_id)
                .order_by(Conversation.updated_at.desc())
            ).first()
            if not conv or not conv.messages:
                return []
            # Return last 10 messages stripped to role+content only
            return [
                {"role": m["role"], "content": m["content"]}
                for m in conv.messages[-10:]
                if "role" in m and "content" in m
            ]
    except Exception as e:
        print(f"[Conversation] Load error (non-fatal): {e}")
        return []


def save_conversation_turn(
    telegram_id: Optional[str],
    market_id: str,
    user_content: str,
    advice: AdviceResponse,
) -> None:
    """
    Appends the user query and assistant advice to the Conversation table.
    Creates the record if it doesn't exist yet.
    The advice object is stored in full so the cache can reconstruct it.
    """
    if not telegram_id:
        return
    try:
        now_str = datetime.now(timezone.utc).isoformat()
        with Session(engine) as session:
            conv = session.exec(
                select(Conversation)
                .where(Conversation.telegram_user_id == telegram_id)
                .where(Conversation.market_id == market_id)
            ).first()
            if conv is None:
                conv = Conversation(
                    telegram_user_id=telegram_id,
                    market_id=market_id,
                    messages=[],
                )
                session.add(conv)
            messages = list(conv.messages or [])
            messages.append({"role": "user", "content": user_content, "ts": now_str})
            messages.append({
                "role": "assistant",
                "content": advice.summary,
                "ts": now_str,
                "advice": advice.dict(),   # full payload for cache reconstruction
            })
            # Keep only the last 40 messages (20 exchanges) to bound DB growth
            conv.messages = messages[-40:]
            conv.updated_at = datetime.utcnow()
            session.commit()
    except Exception as e:
        print(f"[Conversation] Save error (non-fatal): {e}")


# ─────────────────────────────────────────────────────────────
# MAIN ENDPOINT
#
# Flow:
#   1. Rate limit check (Task 3)
#   2. Check advice cache — return stale warning if hit (Task 5a)
#   3. Fetch market data + AI signal directly from Neon
#   4. Load conversation history sliding window (Task 5b)
#   5. Run 3 Tavily searches in parallel (news + social + context)
#   6. Bundle everything into one enriched prompt
#   7. Send to the multi-agent Orchestrator
#   8. Parse → return AdviceResponse
#   9. Save conversation turn + Write AuditLog (Tasks 4 & 5)
# ─────────────────────────────────────────────────────────────

@router.post("/advice", response_model=AdviceResponse)
async def get_advice(request: AdviceRequest):
    tool_calls_used: list[str] = []
    start_time = time.monotonic()
    success = False

    # Task 3: Rate limit check — before any expensive work
    check_rate_limit(request.telegram_id)

    # Policy gate — block prompt injection attempts on the market_id field
    policy = check_policy(request.market_id)
    if not policy["allowed"]:
        raise HTTPException(status_code=400, detail=policy["reason"])

    try:

        if request.premium and not has_premium_access(request.telegram_id, request.market_id):
            return JSONResponse(
                status_code=402,
                content=payment_required_payload(request.market_id),
            )

        # Task 5A: Check advice cache — skip full pipeline if recent result exists
        cached = get_cached_advice(request.telegram_id, request.market_id)
        if cached:
            success = True
            return cached

        # 1. Fetch directly from Neon — no localhost calls
        market_data   = fetch_market_data(request.market_id)
        market_signal = fetch_market_signal(request.market_id)

        # 2. Extract market question
        market_question = (
            market_data.get("question") or
            market_data.get("summary") or
            f"prediction market {request.market_id}"
        ).strip()

        print(f"[Agent] Market {request.market_id}: {market_question}")

        # Task 5b: Load conversation history (sliding window — last 5 exchanges)
        history = load_conversation_history(request.telegram_id, request.market_id)

        # 3. Run 3 Tavily searches in parallel
        search_context = await search_prefetch(market_question)
        tool_calls_used += [
            f"tavily_news: {search_context['queries']['news']}",
            f"tavily_social: {search_context['queries']['social']}",
            f"tavily_context: {search_context['queries']['context']}"
        ]

        # 4. Send everything to the multi-agent Orchestrator
        raw_response, technical_result, sentiment_result = await run_orchestrator(
            market_id=request.market_id,
            market_data=market_data,
            market_signal=market_signal,
            search_context=search_context,
            telegram_id=request.telegram_id,
            premium=request.premium,
            history=history,
            language=request.language
        )

        # 5. Parse → return AdviceResponse (Task 8B: pass agent results for confidence cap)
        response_obj = parse_response(
            raw_response,
            request.market_id,
            tool_calls_used,
            technical_momentum=technical_result.get("momentum", "NEUTRAL"),
            sentiment_label=sentiment_result.get("label", "Neutral"),
        )

        # 6. Post-translate text fields if Swahili is requested
        if request.language == "sw":
            translator = GoogleTranslator(source='en', target='sw')
            try:
                response_obj.summary = translator.translate(response_obj.summary)
                response_obj.why_trending = translator.translate(response_obj.why_trending)
                response_obj.risk_factors = [translator.translate(rf) for rf in response_obj.risk_factors]
                response_obj.disclaimer = translator.translate(response_obj.disclaimer)
                if response_obj.stale_data_warning:
                    response_obj.stale_data_warning = translator.translate(response_obj.stale_data_warning)

                # Manually map the ENUM to ensure reliable translation
                plan_map = {
                    "BUY YES": "NUNUA NDIYO",
                    "BUY NO": "NUNUA HAPANA",
                    "WAIT": "SUBIRI"
                }
                if response_obj.suggested_plan in plan_map:
                    response_obj.suggested_plan = plan_map[response_obj.suggested_plan]

            except Exception as e:
                print(f"[Translation Error] Could not translate to Swahili: {e}")

        success = True

        # Task 5: Save this exchange to conversation history for future context
        save_conversation_turn(
            telegram_id=request.telegram_id,
            market_id=request.market_id,
            user_content=f"/advice {request.market_id}",
            advice=response_obj,
        )

        # ── AUTO-TRADE ENGINE ─────────────────────────────────────────────────
        # Only fires if the user has a telegram_id (anonymous calls are skipped).
        # AutoTradeEngine runs all safety gates internally — this call is always safe.
        # The result is attached to the response so the dashboard / bot can display
        # what happened (executed, blocked, confirm pending, etc.)
        if request.telegram_id:
            try:
                # Build a stable idempotency key: user + market + minute-bucket
                # This prevents double-execution if the client retries within the same minute
                minute_bucket = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
                advice_id = f"{request.telegram_id}-{request.market_id}-{minute_bucket}"

                auto_result = await AutoTradeEngine.execute(
                    market_id=request.market_id,
                    suggested_plan=response_obj.suggested_plan,
                    confidence=response_obj.confidence,
                    telegram_id=request.telegram_id,
                    advice_id=advice_id,
                )
                response_obj.auto_trade_result = auto_result
                print(f"[AutoTrade] {auto_result}")
            except Exception as e:
                # Never let auto-trade errors block the advice response
                print(f"[AutoTrade] Engine error (non-fatal): {e}")
                response_obj.auto_trade_result = {"executed": False, "reason": str(e), "mode": "error"}

        return response_obj

    finally:
        # Task 4: Always write audit log, even on unhandled exceptions
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        write_audit_log(
            telegram_id=request.telegram_id,
            market_id=request.market_id,
            premium=request.premium,
            success=success,
            response_time_ms=elapsed_ms,
        )