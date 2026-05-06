"""
chat.py — POST /agent/chat

General-purpose conversational AI endpoint.
Unlike /agent/advice (which requires a market_id and runs the full
multi-agent pipeline), /agent/chat accepts a free-text question and
returns a conversational reply using the SynthesisAgent directly.

Powers:
  - GlobalChatButton on the dashboard
  - Any future chat interface (Telegram, mobile)

Conversation history is persisted in the Conversation table under
market_id="__global__" so the agent remembers prior exchanges.
"""

import os
import httpx
import logging
import time
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from sqlmodel import Session, select
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

import re
from services.backend.core.policies import check_policy
from services.backend.api.auth import get_current_user
from services.backend.data.database import engine
from services.backend.data.models import Conversation, AuditLog, User

# ─────────────────────────────────────────────────────────────
# Tier Limits  — shared pool: advice + chat count together
# This mirrors how ChatGPT/Claude work: every LLM interaction
# (regardless of how it's phrased) counts against the same quota.
# ─────────────────────────────────────────────────────────────

FREE_COMBINED_LIMIT   = 10   # total LLM calls per 6-hour window
COMBINED_WINDOW_HOURS = 6


def check_combined_rate_limit(user_id: str, premium: bool = False) -> None:
    """
    Counts ALL AuditLog rows with action IN ('advice', 'chat') for this
    user in the last COMBINED_WINDOW_HOURS hours.

    Raises HTTP 429 if the user has exhausted their free quota.
    Premium users are exempt, but premium status must come from verified auth.
    """
    if not user_id or user_id == "anonymous":
        return

    if premium:
        return   # premium — unlimited

    window_start = datetime.now(timezone.utc) - timedelta(hours=COMBINED_WINDOW_HOURS)
    with Session(engine) as session:
        all_logs = session.exec(
            select(AuditLog)
            .where(AuditLog.action.in_(["advice", "chat"]))
            .where(AuditLog.created_at >= window_start)
        ).all()
        user_logs = [l for l in all_logs if (l.telegram_user_id or "").lower() == user_id.lower()]

    if len(user_logs) >= FREE_COMBINED_LIMIT:
        refresh_hint = ""
        if user_logs:
            oldest_ts = min(l.created_at for l in user_logs)
            if oldest_ts.tzinfo is None:
                oldest_ts = oldest_ts.replace(tzinfo=timezone.utc)
            refresh_at     = oldest_ts + timedelta(hours=COMBINED_WINDOW_HOURS)
            refresh_at_eat = refresh_at + timedelta(hours=3)   # EAT = UTC+3
            refresh_str    = refresh_at_eat.strftime("%I:%M %p EAT").lstrip("0")
            refresh_hint   = f" Your limit resets at {refresh_str}."
        raise HTTPException(
            status_code=429,
            detail=(
                f"Your limit will refresh at {refresh_str}."
                " Upgrade to Premium for unlimited access."
            ),
        )

router = APIRouter(prefix="/agent", tags=["Agent"])

OPENROUTER_URL     = os.getenv("OPENROUTER_URL", "https://openrouter.ai/api/v1/chat/completions")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
OPENROUTER_API_KEY_FALLBACK = os.getenv("OPENROUTER_API_KEY_FALLBACK", "").strip()

CHAT_MARKET_ID = "__global__"   # Conversation key for non-market chat sessions

SYSTEM_PROMPT = """You are NORT Bot, an AI assistant for NORT — a Polymarket prediction market trading platform.

You help users understand:
- Prediction markets and how they work
- How to read market signals, odds, and momentum scores
- Paper trading and portfolio management
- The NORT platform features (signals, advice, auto-trade, leaderboard)

Rules:
- Be concise but substantive. Users are on a mobile dashboard.
- Free users: keep replies under 120 words. Premium users: up to 250 words when depth adds value.
- Never invent specific odds or prices — only discuss what the user provides.
- Never recommend real financial action. Always note this is paper trading only.
- Respond in the same language the user writes in.
- If market data is provided to you in the message, use it directly in your response.
- For Premium users: be more analytical and detailed. Reference their conversation history when relevant.
"""

# Regex to detect /advice <market_id> commands in the chat
ADVICE_CMD_RE = re.compile(r'^/advice\s+(\S+)', re.IGNORECASE)

# ─── Models ──────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    user_id: Optional[str] = None    # wallet address or telegram_id
    language: str = "en"

class ChatResponse(BaseModel):
    reply: str
    user_id: Optional[str] = None

# ─── User ID resolver ────────────────────────────────────────────────────────

def _resolve_nort_user_id(user_id: str, session) -> Optional[int]:
    """
    Given whatever string the frontend passes (wallet address or tg_ identifier),
    return the integer User.id from the User table.
    Returns None if no match found — chat still works, just without the FK.
    """
    if not user_id or user_id == "anonymous":
        return None
    try:
        # Path A: tg_XXXXXXX — strip prefix, match on telegram_id
        if user_id.startswith("tg_"):
            telegram_id = user_id[3:]
            user = session.exec(
                select(User).where(User.telegram_id == telegram_id)
            ).first()
            if user:
                return user.id

        # Path B: wallet address — match on wallet_address
        user = session.exec(
            select(User).where(User.wallet_address == user_id.lower())
        ).first()
        if user:
            return user.id

        # Path C: raw telegram_id string (no tg_ prefix, digits only)
        if user_id.isdigit():
            user = session.exec(
                select(User).where(User.telegram_id == user_id)
            ).first()
            if user:
                return user.id

    except Exception as e:
        logger.warning("[Chat] _resolve_nort_user_id failed (non-fatal): %s", e)
    return None


# ─── Conversation helpers ─────────────────────────────────────────────────────

def _load_history(user_id: str) -> list:
    """Load last 10 messages for this user's global chat session."""
    try:
        with Session(engine) as session:
            nort_user_id = _resolve_nort_user_id(user_id, session)

            # Prefer integer FK lookup; fall back to string match
            if nort_user_id:
                conv = session.exec(
                    select(Conversation)
                    .where(Conversation.nort_user_id == nort_user_id)
                    .where(Conversation.market_id == CHAT_MARKET_ID)
                ).first()
            else:
                conv = session.exec(
                    select(Conversation)
                    .where(Conversation.telegram_user_id == user_id)
                    .where(Conversation.market_id == CHAT_MARKET_ID)
                ).first()

            if not conv or not conv.messages:
                return []
            return [
                {"role": m["role"], "content": m["content"]}
                for m in conv.messages[-10:]
                if "role" in m and "content" in m
            ]
    except Exception as e:
        logger.warning("[Chat] History load error (non-fatal): %s", e)
        return []


def _save_turn(user_id: str, user_msg: str, assistant_reply: str) -> None:
    """Append this exchange to the Conversation table."""
    try:
        now_str = datetime.now(timezone.utc).isoformat()
        with Session(engine) as session:
            nort_user_id = _resolve_nort_user_id(user_id, session)

            # Find existing conversation — check by integer ID first
            conv = None
            if nort_user_id:
                conv = session.exec(
                    select(Conversation)
                    .where(Conversation.nort_user_id == nort_user_id)
                    .where(Conversation.market_id == CHAT_MARKET_ID)
                ).first()
            if not conv:
                conv = session.exec(
                    select(Conversation)
                    .where(Conversation.telegram_user_id == user_id)
                    .where(Conversation.market_id == CHAT_MARKET_ID)
                ).first()

            if conv is None:
                conv = Conversation(
                    telegram_user_id=user_id,
                    market_id=CHAT_MARKET_ID,
                    messages=[],
                )
                session.add(conv)

            # Always write nort_user_id if we have it
            if nort_user_id and not conv.nort_user_id:
                conv.nort_user_id = nort_user_id

            messages = list(conv.messages or [])
            messages.append({"role": "user",      "content": user_msg,        "ts": now_str})
            messages.append({"role": "assistant",  "content": assistant_reply, "ts": now_str})
            conv.messages   = messages[-40:]
            conv.updated_at = datetime.utcnow()
            session.commit()
    except Exception as e:
        logger.warning("[Chat] History save error (non-fatal): %s", e)


def _write_advice_audit_log(
    user_id: Optional[str],
    market_id: Optional[str],
    premium: bool,
    success: bool,
    response_time_ms: Optional[int],
) -> None:
    try:
        with Session(engine) as session:
            session.add(AuditLog(
                telegram_user_id=user_id,
                action="advice",
                market_id=market_id,
                premium=premium,
                success=success,
                response_time_ms=response_time_ms,
            ))
            session.commit()
    except Exception as e:
        logger.warning("[Chat] Advice audit write failed (non-fatal): %s", e)

# ─── LLM call ────────────────────────────────────────────────────────────────

def _make_headers(api_key: str) -> dict:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type":  "application/json",
        "HTTP-Referer":  "https://nort.onrender.com",
        "X-Title":       "Nort Chat",
    }

async def _call_llm(messages: list, premium: bool = False) -> str:
    """Send message history to OpenRouter and return the reply text."""
    if not OPENROUTER_API_KEY:
        raise HTTPException(status_code=503, detail="OPENROUTER_API_KEY not configured.")

    # Premium users get Claude Sonnet with more room to elaborate;
    # free users get Llama 3.1 8B — fast and cheap.
    model      = "anthropic/claude-sonnet-4-5" if premium else "meta-llama/llama-3.1-8b-instruct"
    max_tokens = 600 if premium else 300

    payload = {
        "model":      model,
        "messages":   [{"role": "system", "content": SYSTEM_PROMPT}] + messages,
        "max_tokens": max_tokens,
    }

    async def _post(api_key: str):
        async with httpx.AsyncClient(timeout=30) as client:
            return await client.post(OPENROUTER_URL, json=payload, headers=_make_headers(api_key))

    resp = await _post(OPENROUTER_API_KEY)
    if resp.status_code == 429 and OPENROUTER_API_KEY_FALLBACK:
        logger.warning("[Chat] Primary key rate-limited — retrying with fallback key")
        resp = await _post(OPENROUTER_API_KEY_FALLBACK)

    if resp.status_code != 200:
        logger.error("[Chat] OpenRouter error %d: %s", resp.status_code, resp.text[:200])
        raise HTTPException(status_code=503, detail=f"AI service error: {resp.status_code}")

    return resp.json()["choices"][0]["message"]["content"].strip()


# ─── Endpoint ─────────────────────────────────────────────────────────────────

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, current_user: dict = Depends(get_current_user)):
    """
    General-purpose conversational AI endpoint.
    Accepts a free-text message and returns a reply.
    Maintains conversation history per user_id.
    """
    start = time.monotonic()

    # ── Combined rate limit — counts advice + chat calls in the same pool ──
    # This prevents the loophole where a user rephrases an advice question
    # as a chat message to bypass the /advice limit.  Every LLM interaction
    # now draws from the same FREE_COMBINED_LIMIT quota, exactly like
    # ChatGPT / Claude free tiers work.
    # ── Identity: prefer the Privy JWT wallet over the body user_id ────────
    # Body user_id is still accepted for Telegram/internal callers that don't
    # carry a JWT, but cannot override a verified JWT wallet for premium checks.
    jwt_wallet = (current_user.get("wallet") or "").strip() or None
    body_user_id = (request.user_id or "").strip() or None
    user_id = jwt_wallet or body_user_id or "anonymous"

    is_premium_user = False
    if jwt_wallet:
        from services.backend.core.x402_verifier import has_any_confirmed_payment
        is_premium_user = has_any_confirmed_payment(jwt_wallet)

    check_combined_rate_limit(user_id, premium=is_premium_user)

    # Policy gate — block prompt injection
    policy = check_policy(request.message)
    if not policy["allowed"]:
        raise HTTPException(status_code=400, detail=policy["reason"])

    # Build message history — use resolved user_id so JWT users get their own history
    history = _load_history(user_id) if user_id != "anonymous" else []

    # ── Free-tier gate: only /advice commands are allowed ────────────────────
    # General chat (asking questions, rephrasing advice requests, etc.) is a
    # Premium feature.  If a free user sends anything other than /advice <id>,
    # return a hard upgrade prompt without calling the LLM.
    advice_match = ADVICE_CMD_RE.match(request.message.strip())

    if not is_premium_user and not advice_match:
        upgrade_reply = (
            "General chat is a Premium feature.\n\n"
            "Free accounts can use /advice <market_id> to get AI analysis on any market.\n\n"
            "Upgrade to Premium for unlimited chat, deep-dive analysis, and exact entry/exit targets."
        )
        if user_id and user_id != "anonymous":
            _save_turn(user_id, request.message, upgrade_reply)
        return ChatResponse(reply=upgrade_reply, user_id=user_id if user_id != "anonymous" else None)

    # ── /advice <market_id> command handler ──────────────────────────────────
    # If the user types /advice <id>, run the full advice pipeline and return
    # a formatted reply — no LLM chat needed, no redirect.
    if advice_match:
        market_id = advice_match.group(1)
        advice_success = False
        try:
            from services.backend.api.advice import (
                fetch_market_data, fetch_market_signal,
                search_prefetch, parse_response,
                check_rate_limit,
            )
            from services.backend.core.orchestrator import run_orchestrator

            # Resolve premium status for this user
            user_is_premium = is_premium_user  # already computed above from has_any_confirmed_payment

            # Enforce rate limit using resolved user_id (JWT-first)
            check_rate_limit(user_id, premium=user_is_premium)

            market_data   = fetch_market_data(market_id)
            market_signal = fetch_market_signal(market_id)
            market_question = (
                market_data.get("question") or
                f"prediction market {market_id}"
            ).strip()

            search_context = await search_prefetch(market_question)
            raw, technical, sentiment = await run_orchestrator(
                market_id=market_id,
                market_data=market_data,
                market_signal=market_signal,
                search_context=search_context,
                telegram_id=user_id,
                premium=user_is_premium,
                language=request.language,
            )
            resp = parse_response(
                raw, market_id, ["chat_advice"],
                technical_momentum=technical.get("momentum", "NEUTRAL"),
                sentiment_label=sentiment.get("label", "Neutral"),
            )
            advice_success = True

            # Translate advice fields + plan label if Swahili requested (any tier)
            if request.language == "sw":
                from deep_translator import GoogleTranslator
                _tr = GoogleTranslator(source="en", target="sw")
                try:
                    resp.summary      = _tr.translate(resp.summary)
                    resp.why_trending = _tr.translate(resp.why_trending)
                    resp.risk_factors = [_tr.translate(rf) for rf in (resp.risk_factors or [])]
                    resp.disclaimer   = _tr.translate(resp.disclaimer)
                except Exception as _te:
                    logger.warning("[Chat] Swahili translation error (non-fatal): %s", _te)
                plan_map = {"BUY YES": "NUNUA NDIYO", "BUY NO": "NUNUA HAPANA", "WAIT": "SUBIRI"}
                resp.suggested_plan = plan_map.get(resp.suggested_plan, resp.suggested_plan)

            plan_label = resp.suggested_plan

            # Section headers — swap to Swahili if needed
            h_trending  = "INAENDELEA KWA NINI" if request.language == "sw" else "WHY IT'S TRENDING"
            h_risks     = "HATARI KUU"           if request.language == "sw" else "KEY RISKS"
            h_verdict   = "UAMUZI"               if request.language == "sw" else "VERDICT"
            h_confidence = "Uhakika"             if request.language == "sw" else "Confidence"
            upgrade_cta = (
                "Boresha hadi Premium kwa uchambuzi kamili: kwa nini inaendelea, "
                "hatari kuu, na malengo sahihi ya nafasi."
                if request.language == "sw" else
                "Upgrade to Premium for full analysis: why it's trending, "
                "key risks, and exact position targets."
            )

            if user_is_premium:
                # Full deep-dive for premium users
                risks_text = "\n".join(f"- {r}" for r in (resp.risk_factors or []))
                reply = (
                    f"{market_question}\n\n"
                    f"{resp.summary}\n\n"
                    f"{h_trending}\n"
                    f"{resp.why_trending}\n\n"
                    f"{h_risks}\n"
                    f"{risks_text}\n\n"
                    f"{h_verdict}: {plan_label}\n"
                    f"{h_confidence}: {int(resp.confidence * 100)}%\n\n"
                    f"{resp.disclaimer}"
                )
            else:
                # Summary + plan only for free users
                reply = (
                    f"{market_question}\n\n"
                    f"{resp.summary}\n\n"
                    f"{upgrade_cta}\n\n"
                    f"{h_verdict}: {plan_label}\n"
                    f"{h_confidence}: {int(resp.confidence * 100)}%\n\n"
                    f"{resp.disclaimer}"
                )
        except HTTPException as he:
            if he.status_code == 429:
                reply = he.detail
            else:
                reply = f"Sorry, I couldn't fetch advice for market {market_id} right now. Try again or tap a signal card."
        except Exception as e:
            logger.error("[Chat] /advice pipeline error: %s", e)
            reply = f"Sorry, I couldn't fetch advice for market {market_id} right now. Try again or tap a signal card."

        elapsed_ms = int((time.monotonic() - start) * 1000)
        _write_advice_audit_log(
            user_id=user_id if user_id != "anonymous" else None,
            market_id=market_id,
            premium=user_is_premium,
            success=advice_success,
            response_time_ms=elapsed_ms,
        )

        if user_id and user_id != "anonymous":
            _save_turn(user_id, request.message, reply)
        return ChatResponse(reply=reply, user_id=user_id if user_id != "anonymous" else None)

    # ── Normal conversational message ─────────────────────────────────────────
    history.append({"role": "user", "content": request.message})

    # Call LLM — premium users get Claude Sonnet, free get Llama 8B
    reply = await _call_llm(history, premium=is_premium_user)

    # Persist turn under the resolved identity so JWT users keep their history.
    if user_id and user_id != "anonymous":
        _save_turn(user_id, request.message, reply)

    elapsed_ms = int((time.monotonic() - start) * 1000)
    logger.debug("[Chat] user=%s elapsed=%dms reply_len=%d", user_id, elapsed_ms, len(reply))

    try:
        with Session(engine) as session:
            session.add(AuditLog(
                telegram_user_id=user_id if user_id != "anonymous" else None,
                action="chat",
                market_id=None,
                premium=is_premium_user,
                success=True,
                response_time_ms=elapsed_ms,
            ))
            session.commit()
    except Exception as e:
        logger.warning("[Chat] Audit log write failed (non-fatal): %s", e)

    return ChatResponse(reply=reply, user_id=user_id if user_id != "anonymous" else None)
