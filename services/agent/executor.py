"""
executor.py — The AutoTradeEngine (Phase Two: Safety-First Trade Execution)

This is PURE PYTHON code. It is NOT AI. Its job is to be the last line of
defence between the LLM's JSON output and the user's actual USDC wallet.

Key safety rules enforced here (the AI cannot override these):
  1. market_id MUST exist in the Neon DB (blocks prompt injection attacks)
  2. Confidence MUST meet the user's min_confidence threshold
  3. Amount is hard-capped at the user's max_bet_size (even if AI says more)
  4. Idempotency key (advice_id) prevents double-execution on retry
  5. trade_mode gate — "paper" vs "real" routes to different endpoints

Usage (from advice.py or a future /autotrade endpoint):
    from services.agent.executor import AutoTradeEngine
    result = await AutoTradeEngine.execute(advice_response, telegram_id, advice_id)
"""

import asyncio
import hashlib
import httpx
import os
from datetime import datetime, timezone
from typing import Optional
from sqlmodel import Session, select
from dotenv import load_dotenv

load_dotenv()

from services.backend.data.database import engine
from services.backend.data.models import Market, UserPermission, PendingTrade

# Internal execution backend URL (Intern 4's routes)
BACKEND_BASE_URL = os.getenv("BACKEND_BASE_URL", "http://127.0.0.1:8000")
AGENT_HMAC_SECRET = os.getenv("AGENT_HMAC_SECRET", "dev-secret-change-in-prod")

# ─────────────────────────────────────────────────────────────
# HMAC Signing (Internal Agent-to-Agent Security)
# ─────────────────────────────────────────────────────────────

def sign_payload(payload_str: str) -> str:
    """
    Signs the payload with the shared AGENT_HMAC_SECRET.
    Intern 4's route MUST verify this signature before executing any trade.
    """
    import hmac
    return hmac.new(
        AGENT_HMAC_SECRET.encode(),
        payload_str.encode(),
        hashlib.sha256
    ).hexdigest()

# ─────────────────────────────────────────────────────────────
# Market Whitelist Check — Critical Anti-Injection Defence
# ─────────────────────────────────────────────────────────────

def _market_exists_in_db(market_id: str) -> bool:
    """
    Defence 1: Verify the market_id is a real market in our Neon DB.
    If a prompt injection attack tricks the AI into recommending a fake market,
    this check blocks the trade at the Python level — zero LLM involvement.
    """
    try:
        with Session(engine) as session:
            market = session.get(Market, market_id)
            return market is not None
    except Exception as e:
        print(f"[AutoTradeEngine] Market DB check failed: {e}")
        return False  # Fail closed — deny if we can't verify


def _load_user_permission(telegram_id: str) -> Optional["UserPermission"]:
    try:
        with Session(engine) as session:
            return session.exec(
                select(UserPermission)
                .where(UserPermission.telegram_user_id == telegram_id)
            ).first()
    except Exception as e:
        print(f"[AutoTradeEngine] Permission load failed: {e}")
        return None

# ─────────────────────────────────────────────────────────────
# AutoTradeEngine
# ─────────────────────────────────────────────────────────────

class AutoTradeEngine:
    """
    Pure Python safety layer between the AI's advice and actual execution.
    Stateless — all state is read from Neon on each call.
    """

    @staticmethod
    async def execute(
        market_id:      str,
        suggested_plan: str,      # "BUY YES" | "BUY NO" | "WAIT"
        confidence:     float,
        telegram_id:    str,
        advice_id:      str,      # Idempotency key — unique per advice call
        is_leader:      bool = False,  # Copy-trade leaders have a stricter threshold
    ) -> dict:
        """
        Runs all safety checks and, if approved, fires the trade.

        Returns a dict with:
            executed: bool
            reason:   str  (why it was approved OR blocked)
            mode:     str  ("paper" | "real" | "skipped")
        """

        print(f"[AutoTradeEngine] Evaluating: {market_id} | {suggested_plan} | conf={confidence}")

        # ── GATE 0: WAIT means do nothing ────────────────────────────────────
        if suggested_plan == "WAIT":
            return {"executed": False, "reason": "AI recommended WAIT. No trade.", "mode": "skipped"}

        # ── GATE 1: Market must exist in Neon DB (anti-prompt-injection) ─────
        if not _market_exists_in_db(market_id):
            print(f"[AutoTradeEngine] BLOCKED — market_id '{market_id}' not in Neon DB")
            return {
                "executed": False,
                "reason":   f"Market '{market_id}' is not in our approved market list. Trade blocked.",
                "mode":     "blocked"
            }

        # ── GATE 2: Load user permissions ────────────────────────────────────
        perm = _load_user_permission(telegram_id)
        if not perm:
            return {"executed": False, "reason": "No auto-trade permission found. Use /enable_autotrade.", "mode": "skipped"}

        if not perm.auto_trade_enabled:
            return {"executed": False, "reason": "Auto-trade is disabled for this user.", "mode": "skipped"}

        # ── GATE 3: Confidence threshold ─────────────────────────────────────
        # Leaders require 0.80 to protect their followers; solo users need 0.75
        required_confidence = 0.80 if is_leader else perm.min_confidence
        if confidence < required_confidence:
            return {
                "executed": False,
                "reason":   f"Confidence {confidence:.2f} below threshold {required_confidence:.2f}.",
                "mode":     "skipped"
            }

        # ── GATE 4: Determine trade amount (hard-capped at user's limit) ─────
        # Use a default of 10% of the user's max_bet as the base
        raw_amount   = round(perm.max_bet_size * 0.10, 2)
        safe_amount  = min(raw_amount, perm.max_bet_size)  # Hard cap — AI cannot exceed this
        if safe_amount <= 0:
            return {"executed": False, "reason": "Calculated trade amount is $0. Check max_bet_size setting.", "mode": "skipped"}

        # ── Parse the outcome from suggested_plan ────────────────────────────
        outcome = "YES" if "YES" in suggested_plan else "NO"

        # ── GATE 5: Route to paper or real trade ─────────────────────────────
        # ── GATE 5: Route to paper, real, or confirm ─────────────────────────
        # Task 11: "confirm" mode creates a PendingTrade and returns a signal
        # for the Telegram bot to ask the user before any money moves.
        if perm.trade_mode == "confirm":
            from datetime import timedelta
            with Session(engine) as db:
                market = db.get(Market, market_id)
                question = market.question if market else market_id
                pending = PendingTrade(
                    telegram_user_id=telegram_id,
                    market_id=market_id,
                    market_question=question,
                    suggested_plan=suggested_plan,
                    confidence=confidence,
                    amount_usdc=safe_amount,
                    expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
                )
                db.add(pending)
                db.commit()
                db.refresh(pending)
            print(f"[AutoTradeEngine] CONFIRM mode — PendingTrade id={pending.id} created")
            return {
                "executed": False,
                "reason": (
                    f"Confirmation required: {suggested_plan} on {market_id} "
                    f"for ${safe_amount} USDC. "
                    f"Reply YES to confirm (POST /trade/confirm/{pending.id}) "
                    f"or NO to cancel. Expires in 10 minutes."
                ),
                "mode": "confirm",
                "pending_trade_id": pending.id,
            }

        trade_payload = {
            "telegram_id": telegram_id,
            "market_id":   market_id,
            "outcome":     outcome,
            "amount_usdc": safe_amount,
            "confidence":  confidence,
            "advice_id":   advice_id,   # Idempotency key
        }

        payload_str = str(trade_payload)
        signature   = sign_payload(payload_str)

        headers = {
            "Content-Type":       "application/json",
            "X-Agent-Signature":  signature,
        }

        if perm.trade_mode == "paper":
            endpoint = f"{BACKEND_BASE_URL}/papertrade"
        else:
            endpoint = f"{BACKEND_BASE_URL}/trade/real"

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(endpoint, json=trade_payload, headers=headers)
                resp.raise_for_status()
                print(f"[AutoTradeEngine] Trade executed via {endpoint}: {resp.json()}")
                return {
                    "executed": True,
                    "reason":   f"Trade executed: {outcome} on {market_id} for ${safe_amount} USDC",
                    "mode":     perm.trade_mode,
                    "response": resp.json(),
                }

        except httpx.HTTPStatusError as e:
            # Idempotency: 409 Conflict = already executed, NOT an error
            if e.response.status_code == 409:
                return {"executed": False, "reason": "Trade already executed (idempotency check).", "mode": "duplicate"}
            print(f"[AutoTradeEngine] HTTP error {e.response.status_code}: {e.response.text}")
            return {"executed": False, "reason": f"Execution backend error: {e.response.status_code}", "mode": "error"}

        except Exception as e:
            print(f"[AutoTradeEngine] Unexpected error: {e}")
            return {"executed": False, "reason": str(e), "mode": "error"}
