from fastapi import APIRouter, Depends
from pydantic import BaseModel

from services.backend.core.x402_verifier import verify_x402_payment
from services.backend.api.auth import get_current_user

router = APIRouter(prefix="/x402", tags=["x402"])


class VerifyPaymentRequest(BaseModel):
    proof: str
    telegram_id: str | None = None
    user_id: str | None = None
    wallet_address: str | None = None
    market_id: str | None = None


@router.post("/verify")
async def verify_payment(request: VerifyPaymentRequest, current_user: dict = Depends(get_current_user)):
    telegram_id = request.telegram_id or request.user_id or request.wallet_address

    # Optional strict ownership validation — guard against wallet being None
    wallet = (current_user.get("wallet") or "").strip()
    if wallet and wallet.lower() != (telegram_id or "").lower():
        # Backend prefers the authoritative token wallet over the requested param
        telegram_id = wallet
    
    return verify_x402_payment(
        proof=request.proof,
        telegram_id=telegram_id or "",
        market_id=request.market_id,
    )


@router.post("/agent/x402/verify")
async def verify_payment_legacy(request: VerifyPaymentRequest):
    telegram_id = request.telegram_id or request.user_id or request.wallet_address
    return verify_x402_payment(
        proof=request.proof,
        telegram_id=telegram_id or "",
        market_id=request.market_id,
    )
