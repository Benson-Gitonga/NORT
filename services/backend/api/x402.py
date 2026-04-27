from fastapi import APIRouter, Depends
from pydantic import BaseModel

from services.backend.core.x402_verifier import (
    verify_x402_payment,
    GLOBAL_PAYMENT_SCOPE,
    X402_REQUIRED_AMOUNT,
    X402_ASSET,
    X402_CHAIN,
    X402_TREASURY_ADDRESS,
)
from services.backend.api.auth import get_current_user

router = APIRouter(prefix="/x402", tags=["x402"])


# ─── Public payment info ──────────────────────────────────────────────────────

@router.get("/payment-info")
async def payment_info():
    """
    Returns the current premium payment requirements.
    Called by PremiumGate.jsx before initiating a wallet transaction.
    No auth required — this is public information.
    """
    return {
        "amount": X402_REQUIRED_AMOUNT,
        "asset": X402_ASSET,
        "chain": X402_CHAIN,
        "chain_id": 8453,  # Base mainnet
        "treasury": X402_TREASURY_ADDRESS,
        "usdc_contract": "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",
        "description": f"One-time ${X402_REQUIRED_AMOUNT:.2f} {X402_ASSET} payment for Premium access",
    }


class VerifyPaymentRequest(BaseModel):
    proof: str
    telegram_id: str | None = None
    user_id: str | None = None
    wallet_address: str | None = None
    market_id: str | None = None


class UpgradeRequest(BaseModel):
    proof: str
    wallet_address: str | None = None


@router.post("/verify")
async def verify_payment(request: VerifyPaymentRequest, current_user: dict = Depends(get_current_user)):
    telegram_id = request.telegram_id or request.user_id or request.wallet_address

    # Optional strict ownership validation — guard against wallet being None
    wallet = (current_user.get("wallet") or "").strip()
    if wallet and wallet.lower() != (telegram_id or "").lower():
        # Backend prefers the authoritative token wallet over the requested param
        telegram_id = wallet

    return await verify_x402_payment(
        proof=request.proof,
        telegram_id=telegram_id or "",
        market_id=request.market_id,
    )


@router.post("/upgrade")
async def upgrade_to_premium(request: UpgradeRequest, current_user: dict = Depends(get_current_user)):
    """
    Global Premium upgrade — activates Premium for ALL markets for this wallet.
    Called by PremiumGate.jsx when a user pastes a USDC tx hash (or 'demo').
    market_id is always __global__ so one payment covers everything.
    """
    wallet = (current_user.get("wallet") or "").strip() or (request.wallet_address or "").strip()
    return await verify_x402_payment(
        proof=request.proof,
        telegram_id=wallet or "",
        market_id=GLOBAL_PAYMENT_SCOPE,
    )


@router.delete("/dev/reset-payment")
async def dev_reset_payment(wallet_address: str):
    """
    DEV ONLY — deletes all payment records for a wallet so you can re-test
    the free tier and payment flow without switching wallets.
    Remove this endpoint before going to production.
    """
    import os
    if os.getenv("ENVIRONMENT", "development") == "production":
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Not found")

    from sqlmodel import Session, select, delete
    from services.backend.data.models import Payment, User
    from services.backend.data.database import engine
    from services.backend.core.x402_verifier import resolve_user_identity

    with Session(engine) as session:
        # Try canonical wallet lookup first, then fall back to resolve_user_identity
        from services.backend.core.paper_trading import get_user_by_wallet
        addr = wallet_address.strip().lower()
        user = get_user_by_wallet(addr, session) or resolve_user_identity(addr, session)
        if not user:
            return {"deleted": 0, "message": "User not found"}
        result = session.exec(
            select(Payment).where(Payment.user_id == user.id)
        ).all()
        count = len(result)
        for p in result:
            session.delete(p)
        session.commit()
    return {"deleted": count, "wallet": wallet_address, "message": f"Cleared {count} payment(s) — you are now on free tier"}


@router.post("/agent/x402/verify")
async def verify_payment_legacy(request: VerifyPaymentRequest):
    telegram_id = request.telegram_id or request.user_id or request.wallet_address
    return await verify_x402_payment(
        proof=request.proof,
        telegram_id=telegram_id or "",
        market_id=request.market_id,
    )
