"""
Wallet connection routes for Polymarket AI Assistant.
Intern 5 - Wallet Configuration

Endpoints:
  POST /wallet/connect          — Register a real MetaMask wallet
  POST /wallet/privy-webhook    — Auto-called by Privy when user connects
  GET  /wallet/summary          — View paper balance + trade history
"""

import os
import hmac
import json
import hashlib

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
from sqlmodel import Session

from services.backend.data.database import get_session
from services.backend.core.paper_trading import (
    connect_wallet,
    get_user_by_telegram,
    get_wallet_summary,
)

router = APIRouter(tags=["Wallet"])


class WalletConnectRequest(BaseModel):
    wallet_address: str                      # Real MetaMask address e.g. "0xABC...123"
    telegram_id: Optional[str] = None        # Links Telegram bot to this wallet
    username: Optional[str] = None           # Optional display name


@router.post("/wallet/connect")
def wallet_connect(
    request: WalletConnectRequest,
    session: Session = Depends(get_session)
):
    """
    Register a MetaMask wallet into the paper trading system.

    Called by:
    - Dashboard after MetaMask connects (Intern 6)
    - Telegram bot when user links their wallet (Intern 4)

    First time → creates User + WalletConfig with 1000 paper USDC.
    Repeat calls → safe, updates telegram_id if provided.

    Example body:
        { "wallet_address": "0xABC...123", "telegram_id": "987654321" }
    """
    try:
        user = connect_wallet(
            wallet_address=request.wallet_address,
            session=session,
            telegram_id=request.telegram_id,
            username=request.username,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "status": "connected",
        "wallet_address": user.wallet_address,
        "telegram_linked": user.telegram_id is not None,
        "username": user.username,
        "note": "Paper wallet initialized with $1000 USDC (paper only).",
    }


@router.post("/wallet/privy-webhook")
async def privy_webhook(
    request: Request,
    session: Session = Depends(get_session)
):
    """
    Privy auto-calls this when a new user connects their wallet.

    Setup in Privy Dashboard:
      Configuration → Webhooks → Add Webhook
      Event: user.created
      URL:   http://your-server:8000/api/wallet/privy-webhook

    Requires in .env:
      PRIVY_WEBHOOK_SECRET=your-secret-from-privy-dashboard
    """
    body = await request.body()

    privy_signature = request.headers.get("privy-signature", "")
    webhook_secret = os.getenv("PRIVY_WEBHOOK_SECRET", "")

    if not webhook_secret:
        raise HTTPException(status_code=500, detail="PRIVY_WEBHOOK_SECRET not set in .env")

    expected = hmac.new(webhook_secret.encode(), body, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(privy_signature, expected):
        raise HTTPException(status_code=401, detail="Invalid Privy webhook signature.")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON from Privy.")

    # Privy payload: { "type": "user.created", "user": { "wallet": { "address": "0x..." } } }
    wallet_address = (
        payload
        .get("user", {})
        .get("wallet", {})
        .get("address")
    )

    if not wallet_address:
        return {"status": "skipped", "reason": "No wallet address in payload."}

    user = connect_wallet(wallet_address=wallet_address, session=session)

    return {
        "status": "ok",
        "wallet_address": user.wallet_address,
    }


@router.get("/wallet/summary")
def wallet_summary(
    wallet_address: Optional[str] = None,
    telegram_user_id: Optional[str] = None,
    session: Session = Depends(get_session)
):
    """
    Get paper wallet summary. Accepts wallet_address OR telegram_user_id.

    Used by:
    - Dashboard (Intern 6)
    - Telegram /portfolio command (Intern 4)
    - OpenClaw get_wallet_summary() skill (Intern 3)

    Examples:
        GET /wallet/summary?wallet_address=0xABC...123
        GET /wallet/summary?telegram_user_id=987654321
    """
    if not wallet_address and not telegram_user_id:
        raise HTTPException(
            status_code=400,
            detail="Provide either wallet_address or telegram_user_id."
        )

    try:
        summary = get_wallet_summary(
            session=session,
            wallet_address=wallet_address,
            telegram_user_id=telegram_user_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return summary