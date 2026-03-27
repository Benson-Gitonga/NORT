"""
orchestrator.py — The Multi-Agent Orchestrator (Phase Two Core)

Replaces the single call_openclaw() function with a parallel team of sub-agents:

    TechnicalAgent  — Pure Python math on market signals (no LLM cost)
    SentimentAgent  — Mini OpenRouter call with a cheap model (Llama 3 8B)
    RiskAgent       — Pure Python math on user wallet + UserPermission

The SynthesisAgent then receives all 3 structured reports and produces
the final personalized advice using Claude 3 Haiku via OpenRouter.

Usage (from advice.py):
    from services.agent.orchestrator import run_orchestrator
    result = await run_orchestrator(market_id, market_data, market_signal,
                                    search_context, telegram_id, premium, history)
"""

import asyncio
import httpx
import json
import os
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv

load_dotenv(override=True)

OPENROUTER_URL             = os.getenv("OPENROUTER_URL", "https://openrouter.ai/api/v1/chat/completions")
OPENROUTER_API_KEY         = os.getenv("OPENROUTER_API_KEY", "").strip()
OPENROUTER_API_KEY_FALLBACK = os.getenv("OPENROUTER_API_KEY_FALLBACK", "").strip()

def _make_headers(api_key: str) -> dict:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type":  "application/json",
        "HTTP-Referer":  "https://nort.onrender.com",
        "X-Title":       "Nort Advisor",
    }

OPENROUTER_HEADERS = _make_headers(OPENROUTER_API_KEY)

# ─────────────────────────────────────────────────────────────
# TASK 6: PERFORMANCE SUMMARY HELPER
# Reads the last 10 AuditLog entries for this user where
# outcome_correct is not None, and builds a calibration note
# injected into the SynthesisAgent prompt.
# ─────────────────────────────────────────────────────────────

def _build_performance_summary(telegram_id: Optional[str]) -> Optional[str]:
    """
    Returns a one-paragraph performance note for the SynthesisAgent,
    e.g. "Your last 10 advice calls were 7 correct (70% accuracy)..."
    Returns None if there is no feedback data yet.
    """
    if not telegram_id:
        return None
    try:
        from sqlmodel import Session, select
        from services.backend.data.database import engine
        from services.backend.data.models import AuditLog

        with Session(engine) as session:
            logs = session.exec(
                select(AuditLog)
                .where(AuditLog.telegram_user_id == telegram_id)
                .where(AuditLog.action == "advice")
                .where(AuditLog.outcome_correct != None)  # noqa: E711
                .order_by(AuditLog.created_at.desc())
                .limit(10)
            ).all()

        if not logs:
            return None

        correct = sum(1 for l in logs if l.outcome_correct is True)
        total   = len(logs)
        pct     = round((correct / total) * 100)

        trend = ""
        if pct < 50:
            trend = " You have been underperforming recently — consider raising your confidence threshold."
        elif pct >= 80:
            trend = " Your recent accuracy is strong — maintain your current approach."

        return (
            f"PERFORMANCE NOTE: Your last {total} advice calls for this user were "
            f"{correct} correct ({pct}% accuracy).{trend} "
            f"Adjust your confidence score accordingly — do not blindly output 0.85+ "
            f"if your recent track record does not support it."
        )
    except Exception as e:
        print(f"[PerformanceSummary] Failed (non-fatal): {e}")
        return None

# ─────────────────────────────────────────────────────────────
# SUB-AGENT 1: TechnicalAgent (Pure Python — No LLM Cost)
# ─────────────────────────────────────────────────────────────

async def run_technical(market_data: dict, market_signal: dict) -> dict:
    """
    Analyzes raw market numbers and Intern 1's AI signal.
    Returns a structured technical summary — no LLM required.
    """
    try:
        current_odds   = float(market_data.get("current_odds",  0.5))
        previous_odds  = float(market_data.get("previous_odds", 0.5))
        volume         = float(market_data.get("volume",        0.0))
        avg_volume     = float(market_data.get("avg_volume",    0.0))

        odds_movement  = round(current_odds - previous_odds, 4)
        volume_ratio   = round(volume / avg_volume, 2) if avg_volume > 0 else 1.0

        # Simple momentum: how much did odds move in our direction?
        momentum = "BULLISH" if odds_movement > 0.03 else (
                   "BEARISH" if odds_movement < -0.03 else "NEUTRAL")

        # Volume spike = more market activity = more relevant signal
        volume_flag = "HIGH" if volume_ratio > 1.5 else (
                      "LOW"  if volume_ratio < 0.5 else "NORMAL")

        signal_confidence = float(market_signal.get("confidence_score", 0.0)) if market_signal else 0.0
        signal_prediction = market_signal.get("prediction", "N/A") if market_signal else "N/A"

        # Expires soon? Flag it.
        expiry_warning = None
        expires_at = market_data.get("expires_at")
        if expires_at:
            try:
                exp = datetime.fromisoformat(str(expires_at)).replace(tzinfo=timezone.utc)
                now = datetime.now(timezone.utc)
                days_left = (exp - now).days
                if days_left < 3:
                    expiry_warning = f"Market expires in {days_left} day(s)."
            except Exception:
                pass

        return {
            "current_odds":    current_odds,
            "odds_movement":   odds_movement,
            "momentum":        momentum,
            "volume_ratio":    volume_ratio,
            "volume_flag":     volume_flag,
            "signal_prediction":  signal_prediction,
            "signal_confidence":  signal_confidence,
            "expiry_warning":  expiry_warning,
            "ok": True
        }

    except Exception as e:
        print(f"[TechnicalAgent ERROR] {e}")
        return {"ok": False, "error": str(e)}


# ─────────────────────────────────────────────────────────────
# SUB-AGENT 2: SentimentAgent (Mini OpenRouter call — cheap model)
# ─────────────────────────────────────────────────────────────

async def run_sentiment(search_context: dict) -> dict:
    """
    Sends scraped news + social content to Llama 3.3 70B and asks it
    to return a sentiment score 1–10 PLUS a one-sentence reasoning.
    The reasoning is passed into SynthesisAgent so it understands WHY
    the score landed where it did (catches sarcasm, hedging, etc.)
    """
    news_text   = search_context.get("news",   "No news available.")
    social_text = search_context.get("social", "No social data available.")

    prompt = f"""You are a financial sentiment analyzer specializing in prediction markets.
Read the following news and social media content carefully.
Pay close attention to hedging language, sarcasm, and analyst caution phrases.
Return ONLY a JSON object with exactly two fields:
  - "score": integer from 1 to 10 (1=extremely bearish, 5=neutral, 10=extremely bullish)
  - "reason": one sentence explaining the dominant sentiment signal you detected
Do NOT include any other text. JSON only.

Examples of correct output:
{{"score": 4, "reason": "Analysts express caution despite a recent price rally, signaling bearish uncertainty."}}
{{"score": 8, "reason": "Strong institutional buying pressure reported with multiple bullish analyst upgrades."}}

<news>
{news_text[:2000]}
</news>

<social>
{social_text[:1000]}
</social>
"""

    payload = {
        "model": "meta-llama/llama-3.3-70b-instruct",  # Task 1: upgraded from 3B → 70B for accurate financial sentiment
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 80,
    }

    async def _call(api_key: str) -> httpx.Response:
        async with httpx.AsyncClient(timeout=30) as client:
            return await client.post(OPENROUTER_URL, json=payload, headers=_make_headers(api_key))

    try:
        resp = await _call(OPENROUTER_API_KEY)
        # Task 9: fallback key if primary hits 429
        if resp.status_code == 429 and OPENROUTER_API_KEY_FALLBACK:
            print("[SentimentAgent] Primary key rate-limited, retrying with fallback key")
            resp = await _call(OPENROUTER_API_KEY_FALLBACK)
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"].strip()

        # Strip markdown fences if present
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()

        parsed = json.loads(content)
        score  = int(parsed.get("score", 5))
        score  = max(1, min(10, score))  # clamp 1–10
        reason = parsed.get("reason", "No reasoning provided.")

        label = "Bullish" if score >= 7 else ("Bearish" if score <= 3 else "Neutral")
        return {"score": score, "label": label, "reason": reason, "ok": True}

    except Exception as e:
        print(f"[SentimentAgent ERROR] {e}")
        return {"score": 5, "label": "Neutral", "reason": "Sentiment analysis unavailable.", "ok": False, "error": str(e)}


# ─────────────────────────────────────────────────────────────
# SUB-AGENT 3: RiskAgent (Pure Python — No LLM Cost)
# ─────────────────────────────────────────────────────────────

async def run_risk(telegram_id: Optional[str], paper_balance: float = 1000.0,
                   max_bet_size: float = 10.0) -> dict:
    """
    Evaluates how much the user can safely risk on this trade.
    Uses paper_balance (from WalletConfig) and the user's max_bet_size
    from UserPermission. Real wallet balance is injected by advice.py
    from Intern 2's route when available.

    Returns a safe suggested bet size in USDC.
    """
    try:
        # Kelly-lite: never bet more than 5% of portfolio in one trade
        kelly_cap = round(paper_balance * 0.05, 2)

        # Safe bet = lowest of: user's hard limit, Kelly cap
        safe_bet  = round(min(max_bet_size, kelly_cap), 2)

        risk_level = (
            "LOW"    if paper_balance > 500 and safe_bet < 20 else
            "MEDIUM" if paper_balance > 200 else
            "HIGH"
        )

        return {
            "paper_balance":    paper_balance,
            "max_bet_size":     max_bet_size,
            "safe_bet_usdc":    safe_bet,
            "risk_level":       risk_level,
            "ok": True
        }

    except Exception as e:
        print(f"[RiskAgent ERROR] {e}")
        return {"safe_bet_usdc": 5.0, "risk_level": "UNKNOWN", "ok": False, "error": str(e)}


# ─────────────────────────────────────────────────────────────
# SYNTHESIS AGENT — The Boss (OpenRouter Claude Haiku)
# ─────────────────────────────────────────────────────────────

async def run_synthesis(
    market_id: str,
    market_question: str,
    technical: dict,
    sentiment: dict,
    risk: dict,
    search_context: dict,
    history: list,
    premium: bool,
    language: str = "en",
    telegram_id: Optional[str] = None,
) -> str:
    """
    Receives structured reports from 3 sub-agents.
    Builds one clean, enriched prompt and sends to Claude 3 Haiku.
    Uses premium model (Claude 3.5 Sonnet) if premium=True.
    """
    from services.agent.prompt_templates import ADVICE_SYSTEM_PROMPT

    if premium:
        model = "anthropic/claude-3.5-sonnet"
        tier_instruction = (
            "\nPREMIUM MODE: Provide a 3-paragraph deep-dive. Include exact entry/exit odds targets "
            "and a precise position sizing recommendation in USDC."
        )
    else:
        # Use an extremely cheap paid model to bypass strict concurrency rate limits on free OpenRouter endpoints
        model = "meta-llama/llama-3.1-8b-instruct"
        tier_instruction = (
            "\nFREE MODE: Your analysis must be 'vaguely detailed'. Use sophisticated financial and analytical language to sound highly thorough and detailed, but remain entirely vague on actionable intelligence. "
            "Discuss 'shifting momentum', 'building sentiment', and 'complex tech indicators' without giving away the actual specific numbers. Do not give exact odds, entry targets, or precise position sizing. "
            "At the end, strongly encourage the user to unlock PREMIUM advice for the actual numbers, precise odds targets, deep-dive analysis, and position sizing."
        )

    lang_instruction = "Respond entirely in English. Do NOT translate JSON keys."

    # Task 6: inject performance summary so the agent can self-calibrate
    performance_note = _build_performance_summary(telegram_id)
    perf_section = f"\n━━━ PERFORMANCE HISTORY ━━━\n{performance_note}\n" if performance_note else ""

    user_message = f"""/advice {market_id}

MARKET QUESTION: {market_question}

━━━ LANGUAGE INSTRUCTION ━━━
{lang_instruction}
{tier_instruction}

━━━ TECHNICAL ANALYSIS (TechnicalAgent) ━━━
Current Odds:      {technical.get('current_odds', 'N/A')}
Momentum:          {technical.get('momentum', 'N/A')} (movement: {technical.get('odds_movement', 'N/A')})
Volume Activity:   {technical.get('volume_flag', 'N/A')} (ratio vs avg: {technical.get('volume_ratio', 'N/A')})
AI Signal:         {technical.get('signal_prediction', 'N/A')} (confidence: {technical.get('signal_confidence', 'N/A')})
{f"⚠️ EXPIRY WARNING: {technical['expiry_warning']}" if technical.get('expiry_warning') else ''}

━━━ SENTIMENT ANALYSIS (SentimentAgent) ━━━
Sentiment Score:   {sentiment.get('score', 5)}/10
Sentiment Label:   {sentiment.get('label', 'Neutral')}
Sentiment Reason:  {sentiment.get('reason', 'N/A')}

━━━ RISK PROFILE (RiskAgent) ━━━
User Balance:      ${risk.get('paper_balance', 'N/A')} USDC
Risk Level:        {risk.get('risk_level', 'N/A')}
Max Safe Bet:      ${risk.get('safe_bet_usdc', 'N/A')} USDC

━━━ RECENT NEWS (summarized) ━━━
<news>
{search_context.get('news', 'No news available.')[:2000]}
</news>

━━━ SOCIAL BUZZ ━━━
<social>
{search_context.get('social', 'No social data.')[:800]}
</social>
{perf_section}
━━━ YOUR TASK ━━━
Using ALL data above, provide a comprehensive analysis.
The safe_bet_usdc from RiskAgent MUST be reflected in your suggested position size.
Return ONLY valid JSON. The market_id field must be exactly: {market_id}
"""

    messages = []

    # Inject conversation history (sliding window — last 5 exchanges)
    if history:
        for msg in history[-10:]:  # 5 exchanges = 10 messages (user+assistant)
            messages.append({"role": msg["role"], "content": msg["content"]})

    messages.append({"role": "user", "content": user_message})

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": ADVICE_SYSTEM_PROMPT},
            *messages
        ],
    }

    async def _synthesis_call(api_key: str) -> httpx.Response:
        async with httpx.AsyncClient(timeout=120) as client:
            return await client.post(OPENROUTER_URL, json=payload, headers=_make_headers(api_key))

    try:
        resp = await _synthesis_call(OPENROUTER_API_KEY)
        # Task 9: fallback key on 429
        if resp.status_code == 429 and OPENROUTER_API_KEY_FALLBACK:
            print(f"[Synthesis] Primary key rate-limited, retrying with fallback key")
            resp = await _synthesis_call(OPENROUTER_API_KEY_FALLBACK)
        if resp.status_code != 200:
            print(f"[Synthesis] OpenRouter Error ({model}): {resp.status_code} - {resp.text}")
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"[Synthesis] Orchestrator Exception ({model}): {type(e).__name__} - {e}")
        raise e


# ─────────────────────────────────────────────────────────────
# MAIN ORCHESTRATOR ENTRY POINT
# ─────────────────────────────────────────────────────────────

async def run_orchestrator(
    market_id:      str,
    market_data:    dict,
    market_signal:  dict,
    search_context: dict,
    telegram_id:    Optional[str] = None,
    premium:        bool          = False,
    history:        list          = None,
    paper_balance:  float         = 1000.0,
    max_bet_size:   float         = 10.0,
    language:       str           = "en",
) -> str:
    """
    The main entry point. Runs all 3 sub-agents in parallel, then
    feeds their structured reports to the SynthesisAgent.

    Returns a tuple: (raw_llm_response: str, technical: dict, sentiment: dict)
    """
    if history is None:
        history = []

    market_question = (
        market_data.get("question") or
        market_data.get("summary") or
        f"prediction market {market_id}"
    ).strip()

    print(f"[Orchestrator] Running parallel sub-agents for market: {market_id}")

    # ── Run all 3 sub-agents in parallel ─────────────────────
    technical, sentiment, risk = await asyncio.gather(
        run_technical(market_data, market_signal),
        run_sentiment(search_context),
        run_risk(telegram_id, paper_balance, max_bet_size),
    )

    print(f"[Orchestrator] Technical: {technical}")
    print(f"[Orchestrator] Sentiment: {sentiment}")
    print(f"[Orchestrator] Risk:      {risk}")

    # ── Feed all 3 reports to SynthesisAgent ─────────────────
    raw = await run_synthesis(
        market_id=market_id,
        market_question=market_question,
        technical=technical,
        sentiment=sentiment,
        risk=risk,
        search_context=search_context,
        history=history,
        premium=premium,
        language=language,
        telegram_id=telegram_id,
    )

    print(f"[Orchestrator] SynthesisAgent complete.")
    return raw, technical, sentiment
