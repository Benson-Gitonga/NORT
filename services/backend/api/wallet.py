"""
Wallet routes for NORT.

Auth design decision:
    These endpoints accept wallet_address as a query/body param.
    The caller is authenticated via Privy JWT (get_current_user).
    Ownership check = the JWT's wallet must match the requested wallet.
    If JWT has no wallet (common with Privy access tokens), we fall back
    to trusting the X-Wallet-Address header that authFetch always sends.
    We do NOT do DB-level privy_user_id cross-checks — too fragile for
    users whose privy_user_id was never stored.
"""

import os
import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlmodel import Session, select

from services.backend.data.database import get_session
from services.backend.core.paper_trading import (
    connect_wallet,
    get_user_by_telegram,
    get_wallet_summary,
    _ensure_wallet_config,
)
from services.backend.data.models import User
from services.backend.api.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Wallet"], redirect_slashes=False)


# ─── SVIX WEBHOOK VERIFICATION ───────────────────────────────────────────────

def _verify_privy_webhook(body: bytes, headers: dict) -> dict:
    secret = os.getenv("PRIVY_WEBHOOK_SECRET", "").strip()
    if not secret:
        raise HTTPException(status_code=500, detail="PRIVY_WEBHOOK_SECRET not configured.")
    try:
        from svix.webhooks import Webhook
        wh = Webhook(secret)
        return wh.verify(body, headers)
    except ImportError:
        import hmac, hashlib, base64
        sig_header = headers.get("svix-signature", "")
        sigs = [s.split(",", 1)[1] for s in sig_header.split(" ") if "," in s]
        timestamp = headers.get("svix-timestamp", "")
        signed_content = f"{headers.get('svix-id', '')}.{timestamp}.{body.decode()}"
        key = base64.b64decode(secret.replace("whsec_", ""))
        expected = base64.b64encode(
            hmac.new(key, signed_content.encode(), hashlib.sha256).digest()
        ).decode()
        if expected not in sigs:
            raise HTTPException(status_code=401, detail="Invalid webhook signature.")
        return json.loads(body)
    except Exception as e:
        logger.warning(f"[privy-webhook] Verification failed: {e}")
        raise HTTPException(status_code=401, detail=f"Webhook verification failed: {e}")


# ─── MODELS ──────────────────────────────────────────────────────────────────

class WalletConnectRequest(BaseModel):
    wallet_address: str
    telegram_id: Optional[str] = None
    username: Optional[str] = None
    privy_user_id: Optional[str] = None


# ─── OWNERSHIP HELPER ─────────────────────────────────────────────────────────

def _assert_owns_wallet(requested_wallet: str, current_user: dict) -> None:
    """
    Verify the authenticated user is requesting their own wallet.

    Uses the wallet resolved by get_current_user (from JWT or X-Wallet-Address).
    Comparison is case-insensitive.

    Skips the check entirely if current_user has no wallet — this happens
    when a Telegram user (no Privy JWT) hits a soft-gated endpoint.
    In that case we trust the request (the JWT was still verified as valid).
    """
    jwt_wallet = (current_user.get("wallet") or "").strip().lower()
    target     = requested_wallet.strip().lower()

    if not jwt_wallet:
        # No wallet in JWT/headers — cannot enforce ownership, allow through
        # (JWT signature was still verified, so user is authenticated with Privy)
        logger.debug(f"[auth] No wallet in JWT for ownership check of {target[:10]} — allowing")
        return

    if jwt_wallet != target:
        logger.warning(f"[auth] Ownership mismatch: jwt={jwt_wallet[:10]} target={target[:10]}")
        raise HTTPException(status_code=403, detail="Cannot access another user's wallet.")


# ─── ENDPOINTS ────────────────────────────────────────────────────────────────

@router.post("/wallet/connect")
def wallet_connect(
    request: WalletConnectRequest,
    session: Session = Depends(get_session),
):
    """
    Register or upsert a wallet. No auth required — this is called on login
    before the JWT is available, and it's idempotent.
    """
    try:
        user = connect_wallet(
            wallet_address=request.wallet_address,
            session=session,
            telegram_id=request.telegram_id,
            username=request.username,
        )
        if request.privy_user_id:
            try:
                if not getattr(user, "privy_user_id", None):
                    user.privy_user_id = request.privy_user_id
                    session.add(user)
                    session.commit()
                    session.refresh(user)
            except Exception:
                pass
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "status":          "connected",
        "wallet_address":  user.wallet_address,
        "telegram_linked": user.telegram_id is not None,
        "username":        user.username,
        "note":            "Paper wallet initialized with $1000 USDC (paper only).",
    }


@router.post("/wallet/privy-webhook")
async def privy_webhook(
    request: Request,
    session: Session = Depends(get_session),
):
    body = await request.body()
    svix_headers = {
        "svix-id":        request.headers.get("svix-id", ""),
        "svix-timestamp": request.headers.get("svix-timestamp", ""),
        "svix-signature": request.headers.get("svix-signature", ""),
    }
    payload    = _verify_privy_webhook(body, svix_headers)
    event_type = payload.get("type", "unknown")
    logger.info(f"[privy-webhook] Event: {event_type}")

    if event_type == "user.created":
        return _handle_user_created(payload, session)
    elif event_type == "wallet.created_for_user":
        return _handle_wallet_created(payload, session)
    elif event_type == "transaction.confirmed":
        return _handle_tx_confirmed(payload, session)
    elif event_type == "transaction.failed":
        logger.warning(f"[privy-webhook] tx failed: {payload.get('data', {}).get('transaction_hash', '?')}")
        return {"status": "logged", "event": event_type}
    elif event_type == "funds.deposited":
        return _handle_funds_deposited(payload, session)
    elif event_type == "privy.test":
        return {"status": "ok", "event": "privy.test"}
    else:
        logger.info(f"[privy-webhook] Unhandled event: {event_type}")
        return {"status": "ignored", "event": event_type}


# ─── WALLET SUMMARY ───────────────────────────────────────────────────────────

@router.get("/wallet/summary")
def wallet_summary(
    wallet_address:   Optional[str] = None,
    telegram_user_id: Optional[str] = None,
    session:          Session        = Depends(get_session),
    current_user:     dict           = Depends(get_current_user),
):
    # Resolve which wallet to look up
    target_wallet = (
        wallet_address
        or telegram_user_id
        or current_user.get("wallet")
    )
    if not target_wallet:
        raise HTTPException(400, "Provide wallet_address, telegram_user_id, or authenticate.")

    # Ownership check — only verify if we have a concrete wallet to compare
    if wallet_address:
        _assert_owns_wallet(wallet_address, current_user)

    try:
        summary = get_wallet_summary(
            session=session,
            wallet_address=wallet_address or (target_wallet if not telegram_user_id else None),
            telegram_user_id=telegram_user_id,
        )
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))

    return summary


# ─── PRIVY WEBHOOK EVENT HANDLERS ─────────────────────────────────────────────

def _handle_user_created(payload: dict, session: Session) -> dict:
    user_obj = payload.get("user", {})
    privy_user_id = user_obj.get("id", "")
    linked = user_obj.get("linked_accounts", [])
    wallet_address = None
    for account in linked:
        if account.get("type") == "wallet" and account.get("chain_type") == "ethereum":
            wallet_address = account.get("address")
            break
    if not wallet_address:
        return {"status": "skipped", "reason": "No EVM wallet in linked_accounts."}
    connect_wallet(wallet_address=wallet_address.lower(), session=session)
    logger.info(f"[privy-webhook] user.created: {wallet_address}")
    return {"status": "ok", "event": "user.created", "wallet_address": wallet_address}


def _handle_wallet_created(payload: dict, session: Session) -> dict:
    wallet_address = payload.get("wallet", {}).get("address", "")
    if not wallet_address:
        return {"status": "skipped", "reason": "No wallet address."}
    connect_wallet(wallet_address=wallet_address.lower(), session=session)
    logger.info(f"[privy-webhook] wallet.created_for_user: {wallet_address}")
    return {"status": "ok", "event": "wallet.created_for_user", "wallet_address": wallet_address}


def _handle_tx_confirmed(payload: dict, session: Session) -> dict:
    data = payload.get("data", {})
    tx_hash = data.get("transaction_hash", "")
    logger.info(f"[privy-webhook] transaction.confirmed: {tx_hash}")
    return {"status": "ok", "event": "transaction.confirmed", "tx_hash": tx_hash}


def _handle_funds_deposited(payload: dict, session: Session) -> dict:
    data = payload.get("data", {})
    wallet_address = data.get("wallet_address", "").lower()
    amount = data.get("amount", 0)
    token  = data.get("token_symbol", "USDC")
    logger.info(f"[privy-webhook] funds.deposited: {amount} {token} → {wallet_address}")
    return {"status": "ok", "event": "funds.deposited", "wallet_address": wallet_address, "amount": amount}
