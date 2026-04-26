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


@router.post("/agent/x402/verify")
async def verify_payment_legacy(request: VerifyPaymentRequest):
    telegram_id = request.telegram_id or request.user_id or request.wallet_address
    return await verify_x402_payment(
        proof=request.proof,
        telegram_id=telegram_id or "",
        market_id=request.market_id,
    )
