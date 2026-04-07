import json
import re
import time
import httpx
import os
import asyncio
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Depends, Request
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
from services.backend.core.x402_verifier import has_premium_access, has_any_confirmed_payment, payment_required_payload
from services.backend.data.database import engine
from services.backend.data.models import Market, AISignal, AuditLog, Conversation
from services.backend.api.auth import get_current_user

router = APIRouter(prefix="/agent", tags=["Agent"])

OPENROUTER_URL = os.getenv("OPENROUTER_URL", "https://openrouter.ai/api/v1/chat/completions")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "").strip()

# ─────────────────────────────────────────────────────────────
# Tier Limits (defined at top so every endpoint can reference them)
# ─────────────────────────────────────────────────────────────

FREE_DAILY_LIMIT     = 10   # free users: 10 advice calls per day
PREMIUM_HOURLY_LIMIT = 10   # premium users: 10 per hour (effectively unlimited for normal use)

# ─────────────────────────────────────────────────────────────
# Request / Response Models
# ─────────────────────────────────────────────────────────────

class AdviceRequest(BaseModel):
    market_id: str
    telegram_id: Optional[str] = None   # wallet address for dashboard users, telegram ID for bot users
    premium: bool = False
    language: str = "en"
    user_message: Optional[str] = None

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
# NORT Bot Caller — single-shot enriched prompt
# ─────────────────────────────────────────────────────────────

async def call_nort_bot(
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

    print(f"[NORT Bot] Sending prompt for market {market_id}")

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
            raise HTTPException(status_code=503, detail="NORT Bot gateway unreachable")
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=503, detail=f"NORT Bot error {e.response.status_code}")

# ─────────────────────────────────────────────────────────────
# Debug Endpoint
# ─────────────────────────────────────────────────────────────

@router.get("/usage")
def get_advice_usage(
    wallet_address: str = "",
    current_user: dict = Depends(get_current_user),
):
    """
    Returns how many free advice calls the user has made today
    and whether they have premium access.
    Called by the frontend useTier hook.

    Identity resolution (most → least authoritative):
      1. JWT token wallet  (current_user["wallet"] — set by Privy auth)
      2. wallet_address query param  (fallback for unauthenticated / Telegram users)
    This ensures the same identity used by /agent/advice and /x402/verify
    is used here, preventing mismatches after a demo or real payment.
    """
    # Prefer the JWT-verified wallet over the raw query param
    effective_wallet = (current_user.get("wallet") or "").strip() or wallet_address.strip()

    window_start = datetime.now(timezone.utc) - timedelta(hours=24)
    with Session(engine) as session:
        all_logs = session.exec(
            select(AuditLog)
            .where(AuditLog.action == "advice")
            .where(AuditLog.created_at >= window_start)
        ).all()
        logs = [l for l in all_logs if (l.telegram_user_id or "").lower() == effective_wallet.lower()]
    used_today = len(logs)
    is_premium = any(l.premium for l in logs)
    if not is_premium:
        is_premium = has_any_confirmed_payment(effective_wallet)
    return {
        "wallet_address": effective_wallet,
        "used_today":     used_today,
        "daily_limit":    FREE_DAILY_LIMIT,
        "is_premium":     is_premium,
        "remaining":      max(0, FREE_DAILY_LIMIT - used_today) if not is_premium else None,
    }


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
    def _extract_string_field(blob: str, field: str) -> Optional[str]:
        pattern = rf'"{re.escape(field)}"\s*:\s*"((?:\\.|[^"\\])*)"'
        match = re.search(pattern, blob, flags=re.S)
        if not match:
            return None
        try:
            return json.loads(f'"{match.group(1)}"')
        except Exception:
            return match.group(1)

    def _extract_number_field(blob: str, field: str) -> Optional[float]:
        pattern = rf'"{re.escape(field)}"\s*:\s*(-?\d+(?:\.\d+)?)'
        match = re.search(pattern, blob)
        if not match:
            return None
        try:
            return float(match.group(1))
        except Exception:
            return None

    def _extract_string_list_field(blob: str, field: str) -> Optional[list[str]]:
        pattern = rf'"{re.escape(field)}"\s*:\s*\[(.*?)\]'
        match = re.search(pattern, blob, flags=re.S)
        if not match:
            return None
        items = re.findall(r'"((?:\\.|[^"\\])*)"', match.group(1), flags=re.S)
        values: list[str] = []
        for item in items:
            try:
                values.append(json.loads(f'"{item}"'))
            except Exception:
                values.append(item)
        return values

    def _salvage_partial_response(blob: str) -> Optional[dict]:
        salvaged = {
            "market_id": _extract_string_field(blob, "market_id") or market_id,
            "summary": _extract_string_field(blob, "summary"),
            "why_trending": _extract_string_field(blob, "why_trending"),
            "risk_factors": _extract_string_list_field(blob, "risk_factors"),
            "suggested_plan": _extract_string_field(blob, "suggested_plan"),
            "confidence": _extract_number_field(blob, "confidence"),
            "stale_data_warning": _extract_string_field(blob, "stale_data_warning"),
        }
        if not any(salvaged.values()):
            return None
        if not salvaged["summary"]:
            return None
        salvaged["why_trending"] = salvaged["why_trending"] or "Model returned a partial response."
        salvaged["risk_factors"] = salvaged["risk_factors"] or ["Partial AI response"]
        salvaged["suggested_plan"] = salvaged["suggested_plan"] or "WAIT"
        salvaged["confidence"] = salvaged["confidence"] if salvaged["confidence"] is not None else 0.4
        salvaged["stale_data_warning"] = salvaged["stale_data_warning"] or "Recovered from partial AI response."
        return salvaged

    cleaned = raw.strip()

    # Strip markdown fences (```json ... ``` or ``` ... ```)
    if "```" in cleaned:
        parts = cleaned.split("```")
        for part in parts:
            candidate = part.strip()
            if candidate.startswith("json"):
                candidate = candidate[4:].strip()
            if candidate.startswith("{"):
                cleaned = candidate
                break

    # Extract the outermost JSON object
    start = cleaned.find("{")
    end = cleaned.rfind("}") + 1
    if start != -1 and end > start:
        cleaned = cleaned[start:end]

    # Log the raw response to help debug future failures
    if not cleaned.startswith("{"):
        print(f"[ParseResponse] WARNING: Could not find JSON in response. Raw (first 300 chars): {raw[:300]}")

    # If response was truncated mid-JSON, attempt to close it so json.loads has a chance
    if cleaned.startswith("{") and not cleaned.endswith("}"):
        print(f"[ParseResponse] WARNING: JSON appears truncated — attempting recovery")
        # Close any open string, then close the object
        if cleaned.count('"') % 2 != 0:
            cleaned += '"'
        cleaned += ', "suggested_plan": "WAIT", "confidence": 0.4, "disclaimer": "This is not financial advice.", "stale_data_warning": "Response was truncated."}'

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        print(f"[ParseResponse] JSON decode failed. Cleaned (first 300 chars): {cleaned[:300]}")
        salvaged = _salvage_partial_response(cleaned)
        if salvaged:
            print("[ParseResponse] Recovered partial response via field extraction")
            data = salvaged
        else:
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

def check_rate_limit(telegram_id: str, premium: bool = False) -> None:
    if not telegram_id:
        return
    if premium:
        window_start = datetime.now(timezone.utc) - timedelta(hours=1)
        limit = PREMIUM_HOURLY_LIMIT
        label = f"{PREMIUM_HOURLY_LIMIT} calls per hour"
    else:
        window_start = datetime.now(timezone.utc) - timedelta(hours=24)
        limit = FREE_DAILY_LIMIT
        label = f"{FREE_DAILY_LIMIT} free advice calls per day"

    with Session(engine) as session:
        all_logs = session.exec(
            select(AuditLog)
            .where(AuditLog.action == "advice")
            .where(AuditLog.created_at >= window_start)
        ).all()
        count = [l for l in all_logs if (l.telegram_user_id or "").lower() == telegram_id.lower()]
    if len(count) >= limit:
        upgrade_hint = " Upgrade to Premium for unlimited advice." if not premium else ""
        raise HTTPException(
            status_code=429,
            detail=f"Limit reached: {label}.{upgrade_hint}"
        )


def write_audit_log(
    telegram_id: Optional[str],
    market_id: Optional[str],
    premium: bool,
    success: bool,
    response_time_ms: Optional[int],
    action: str = "advice",
) -> None:
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

def get_cached_advice(
    telegram_id: Optional[str],
    market_id: str,
    *,
    allow_cache: bool = True,
) -> Optional[AdviceResponse]:
    if not allow_cache:
        return None
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
    user_id: Optional[str],
    market_id: str,
    user_content: str,
    advice: AdviceResponse,
) -> None:
    if not user_id:
        return
    try:
        now_str = datetime.now(timezone.utc).isoformat()
        with Session(engine) as session:
            conv = session.exec(
                select(Conversation)
                .where(Conversation.telegram_user_id == user_id)
                .where(Conversation.market_id == market_id)
            ).first()
            if conv is None:
                conv = Conversation(
                    telegram_user_id=user_id,
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
async def get_advice(
    request: Request,
    body_req: AdviceRequest,
    current_user: dict = Depends(get_current_user),
):
    tool_calls_used: list[str] = []
    start_time = time.monotonic()
    success = False

    effective_user_id = current_user.get("wallet") or body_req.telegram_id

    # ── Auto-upgrade: if the user has a confirmed payment, always give Premium ──
    # This fixes state-lag where a user has paid but the frontend still sends
    # premium=False because the local tier state hasn't refreshed yet.
    if not body_req.premium and effective_user_id:
        if has_any_confirmed_payment(effective_user_id):
            print(f"[AutoUpgrade] Upgrading {effective_user_id} to Premium (confirmed payment found)")
            body_req.premium = True

    # Rate limit check
    check_rate_limit(effective_user_id, body_req.premium)

    # Policy gate
    policy = check_policy(body_req.market_id)
    if not policy["allowed"]:
        raise HTTPException(status_code=400, detail=policy["reason"])

    try:
        if body_req.premium and not has_premium_access(effective_user_id, body_req.market_id):
            return JSONResponse(
                status_code=402,
                content=payment_required_payload(body_req.market_id),
            )

        allow_cache = (not body_req.premium) and (not body_req.user_message)
        cached = get_cached_advice(effective_user_id, body_req.market_id, allow_cache=allow_cache)
        if cached:
            success = True
            return cached

        market_data   = fetch_market_data(body_req.market_id)
        market_signal = fetch_market_signal(body_req.market_id)

        market_question = (
            market_data.get("question") or
            market_data.get("summary") or
            f"prediction market {body_req.market_id}"
        ).strip()

        print(f"[Agent] Market {body_req.market_id}: {market_question}")

        history = load_conversation_history(effective_user_id, body_req.market_id) if body_req.premium else []
        if body_req.user_message:
            history = [*history, {"role": "user", "content": body_req.user_message}]

        search_context = await search_prefetch(market_question)
        tool_calls_used += [
            f"tavily_news: {search_context['queries']['news']}",
            f"tavily_social: {search_context['queries']['social']}",
            f"tavily_context: {search_context['queries']['context']}",
        ]

        raw_response, technical_result, sentiment_result = await run_orchestrator(
            market_id=body_req.market_id,
            market_data=market_data,
            market_signal=market_signal,
            search_context=search_context,
            telegram_id=effective_user_id,
            premium=body_req.premium,
            history=history,
            language=body_req.language,
        )

        response_obj = parse_response(
            raw_response,
            body_req.market_id,
            tool_calls_used,
            technical_momentum=technical_result.get("momentum", "NEUTRAL"),
            sentiment_label=sentiment_result.get("label", "Neutral"),
        )

        if body_req.premium and body_req.language == "sw":
            translator = GoogleTranslator(source="en", target="sw")
            try:
                response_obj.summary       = translator.translate(response_obj.summary)
                response_obj.why_trending  = translator.translate(response_obj.why_trending)
                response_obj.risk_factors  = [translator.translate(rf) for rf in response_obj.risk_factors]
                response_obj.disclaimer    = translator.translate(response_obj.disclaimer)
                plan_map = {"BUY YES": "NUNUA NDIYO", "BUY NO": "NUNUA HAPANA", "WAIT": "SUBIRI"}
                if response_obj.suggested_plan in plan_map:
                    response_obj.suggested_plan = plan_map[response_obj.suggested_plan]
            except Exception as e:
                print(f"[Translation Error] {e}")

        success = True

        save_conversation_turn(
            user_id=effective_user_id,
            market_id=body_req.market_id,
            user_content=body_req.user_message or f"/advice {body_req.market_id}",
            advice=response_obj,
        )

        if effective_user_id:
            try:
                minute_bucket = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
                advice_id = f"{effective_user_id}-{body_req.market_id}-{minute_bucket}"
                auto_result = await AutoTradeEngine.execute(
                    market_id=body_req.market_id,
                    suggested_plan=response_obj.suggested_plan,
                    confidence=response_obj.confidence,
                    telegram_id=effective_user_id,
                    advice_id=advice_id,
                )
                response_obj.auto_trade_result = auto_result
            except Exception as e:
                print(f"[AutoTrade] Engine error (non-fatal): {e}")
                response_obj.auto_trade_result = {"executed": False, "reason": str(e), "mode": "error"}

        return response_obj

    finally:
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        write_audit_log(
            telegram_id=effective_user_id,
            market_id=body_req.market_id,
            premium=body_req.premium,   # reflects auto-upgrade if it fired
            success=success,
            response_time_ms=elapsed_ms,
        )
