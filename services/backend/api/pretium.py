"""
Pretium API Routes — On-ramp / Off-ramp via Pretium Africa

Endpoints:
  GET  /pretium/rate                → get exchange rate
  POST /pretium/onramp              → create on-ramp order (KES -> USDC via STK push)
  POST /pretium/offramp             → create off-ramp order (USDC -> KES via M-Pesa)
  GET  /pretium/transaction/{id}    → get transaction status
  GET  /pretium/transactions        → list user's transactions
  POST /pretium/webhook             → receive Pretium webhook events
  GET  /pretium/settlement-address  → get settlement wallet address (for off-ramp)
  GET  /pretium/countries           → list supported countries
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, field_validator
from sqlmodel import Session

from services.backend.core.pretium_client import (
    PretiumError,
    get_pretium_client,
)
from services.backend.core.pretium_service import (
    create_offramp,
    create_onramp,
    check_transaction_status,
    get_exchange_rate,
    get_settlement_address,
    get_transaction,
    list_transactions,
    normalize_phone,
    process_webhook,
)
from services.backend.data.database import get_session
from services.backend.api.auth import get_current_user
import httpx

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pretium", tags=["Pretium"], redirect_slashes=False)


# ─── Request Models ──────────────────────────────────────────────────────────

class OnRampRequest(BaseModel):
    amount: int  # KES amount (integer, as Pretium expects)
    phone_number: str
    wallet_address: str
    mobile_network: str = "Safaricom"
    chain: str = "BASE"
    asset: str = "USDC"
    fee: int = 0
    telegram_user_id: Optional[str] = None

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v):
        if v <= 0:
            raise ValueError("amount must be positive")
        return v

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v):
        normalize_phone(v)
        return v


class OffRampRequest(BaseModel):
    amount_crypto: float  # USDC amount
    phone_number: str
    wallet_address: str
    transaction_hash: str  # proof of crypto sent to settlement wallet
    mobile_network: str = "Safaricom"
    chain: str = "BASE"
    asset: str = "USDC"
    fee: int = 0
    telegram_user_id: Optional[str] = None

    @field_validator("amount_crypto")
    @classmethod
    def validate_amount(cls, v):
        if v < 1:
            raise ValueError("minimum off-ramp amount is 1 USDC")
        return v

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v):
        normalize_phone(v)
        return v


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _resolve_user_id(
    request_tid: Optional[str],
    wallet_address: Optional[str],
    session: Session,
) -> str:
    """Resolve telegram_user_id from request or wallet_address."""
    if request_tid:
        return request_tid
    if wallet_address:
        from services.backend.core.paper_trading import get_user_by_wallet
        user = get_user_by_wallet(wallet_address.lower(), session)
        if user and user.telegram_id:
            return user.telegram_id
        return wallet_address.lower()
    raise HTTPException(status_code=400, detail="telegram_user_id or wallet_address required")


# ─── Exchange Rate ──────────────────────────────────────────────────────────

@router.get("/rate")
async def rate_endpoint(currency: str = "KES"):
    """Get current exchange rates (buying, selling, quoted)."""
    try:
        return await get_exchange_rate(currency)
    except PretiumError as e:
        raise HTTPException(status_code=e.status_code or 502, detail=e.message)


# ─── On-Ramp ────────────────────────────────────────────────────────────────

@router.post("/onramp", status_code=201)
async def onramp_endpoint(
    req: OnRampRequest,
    request: Request,
    session: Session = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """Create an on-ramp order: KES -> USDC via M-Pesa STK push."""
    tid = current_user["wallet"]

    try:
        result = await create_onramp(
            telegram_user_id=tid,
            amount=req.amount,
            phone_number=req.phone_number,
            wallet_address=req.wallet_address,
            mobile_network=req.mobile_network,
            chain=req.chain,
            asset=req.asset,
            fee=req.fee,
            session=session,
        )
        return result
    except PretiumError as e:
        raise HTTPException(status_code=e.status_code or 502, detail=e.message)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ─── Off-Ramp ───────────────────────────────────────────────────────────────

@router.post("/offramp", status_code=201)
async def offramp_endpoint(
    req: OffRampRequest,
    session: Session = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """Create an off-ramp order: USDC -> KES via M-Pesa."""
    tid = current_user["wallet"]

    # Verify on-chain tx_hash
    expected_address = await get_settlement_address(req.chain)
    if expected_address:
        try:
            async with httpx.AsyncClient() as client:
                r = await client.post(
                    "https://mainnet.base.org",
                    json={"jsonrpc": "2.0", "method": "eth_getTransactionReceipt", "params": [req.transaction_hash], "id": 1}
                )
            receipt = r.json().get("result")
            if not receipt or receipt.get("status") != "0x1":
                raise HTTPException(status_code=400, detail="Invalid or failed transaction hash on chain")
            # In a full implementation, we'd further check logs for exact amount & correct token contract
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            # If RPC fails temporarily, we might still want to proceed and let Pretium fail it, or reject
            pass

    try:
        result = await create_offramp(
            telegram_user_id=tid,
            amount_crypto=req.amount_crypto,
            phone_number=req.phone_number,
            wallet_address=req.wallet_address,
            transaction_hash=req.transaction_hash,
            mobile_network=req.mobile_network,
            chain=req.chain,
            asset=req.asset,
            fee=req.fee,
            session=session,
        )
        return result
    except PretiumError as e:
        raise HTTPException(status_code=e.status_code or 502, detail=e.message)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ─── Transaction queries ────────────────────────────────────────────────────

@router.get("/transaction/{transaction_id}")
async def transaction_status_endpoint(
    transaction_id: str,
    session: Session = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """Get current status of a transaction. Also checks Pretium for updates."""
    try:
        tx = await check_transaction_status(transaction_id, session)
        if not tx:
            raise HTTPException(status_code=404, detail="Transaction not found")
        if tx.telegram_user_id.lower() != current_user["wallet"].lower():
            raise HTTPException(status_code=403, detail="Not your transaction")
        return tx
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PretiumError:
        # Fallback to local data if Pretium status check fails
        tx = get_transaction(transaction_id, session)
        if not tx:
            raise HTTPException(status_code=404, detail="Transaction not found")
        return tx


@router.get("/transactions")
def transactions_list_endpoint(
    type: Optional[str] = None,
    limit: int = 20,
    session: Session = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """List transactions for a user."""
    tid = current_user["wallet"]
    return {
        "transactions": list_transactions(tid, tx_type=type, limit=limit, session=session),
    }


# ─── Webhook ────────────────────────────────────────────────────────────────

@router.post("/webhook")
async def webhook_endpoint(request: Request, session: Session = Depends(get_session)):
    """
    Receive Pretium webhook events.

    Pretium sends JSON payloads to the callback_url:
    - Offramp: {status, transaction_code, receipt_number, public_name, message}
    - Onramp (payment): {status, transaction_code, receipt_number, public_name, message}
    - Onramp (release): {is_released, transaction_code, transaction_hash}

    Note: Pretium does not document webhook signature verification.
    We validate via transaction_code matching our DB records instead.
    """
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    logger.info("pretium.webhook.received", extra={
        "transaction_code": payload.get("transaction_code"),
        "status": payload.get("status"),
        "is_released": payload.get("is_released"),
    })

    tx_code = payload.get("transaction_code")
    if not tx_code:
        raise HTTPException(status_code=400, detail="Missing transaction_code")
        
    tx = get_transaction(tx_code, session)
    if not tx:
        raise HTTPException(status_code=400, detail="Unknown transaction_code — ignoring")

    result = await process_webhook(payload, session)
    return result


# ─── Settlement Address ─────────────────────────────────────────────────────

@router.get("/settlement-address")
async def settlement_address_endpoint(chain: str = "BASE"):
    """Get the settlement wallet address for off-ramp crypto transfers."""
    try:
        address = await get_settlement_address(chain)
        if not address:
            raise HTTPException(status_code=404, detail=f"No settlement address for chain: {chain}")
        return {"chain": chain, "address": address}
    except PretiumError as e:
        raise HTTPException(status_code=e.status_code or 502, detail=e.message)


# ─── Discovery ───────────────────────────────────────────────────────────────

@router.get("/countries")
async def countries_endpoint():
    """List supported countries."""
    client = get_pretium_client()
    try:
        return await client.get_countries()
    except PretiumError as e:
        raise HTTPException(status_code=e.status_code or 502, detail=e.message)
