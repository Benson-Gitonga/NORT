import os
from datetime import datetime

from sqlmodel import Session, select

from services.backend.core.paper_trading import connect_wallet, get_user_by_telegram, get_user_by_wallet
from services.backend.data.database import engine
from services.backend.data.models import Payment, User

X402_REQUIRED_AMOUNT = float(os.getenv("X402_REQUIRED_AMOUNT", "0.10"))
X402_ASSET = os.getenv("X402_ASSET", "USDC")
X402_CHAIN = os.getenv("X402_CHAIN", "Base")
X402_TREASURY_ADDRESS = os.getenv("NORT_TREASURY_ADDRESS", "NORT_TREASURY_ADDRESS")
GLOBAL_PAYMENT_SCOPE = "__global__"


def payment_required_payload(market_id: str) -> dict:
    return {
        "message": "Payment required",
        "market_id": market_id,
        "amount": X402_REQUIRED_AMOUNT,
        "asset": X402_ASSET,
        "chain": X402_CHAIN,
        "address": X402_TREASURY_ADDRESS,
    }


def has_premium_access(telegram_id: str | None, market_id: str) -> bool:
    if not telegram_id:
        return False

    with Session(engine) as session:
        user = resolve_user_identity(str(telegram_id), session)
        if not user:
            return False

        payment = session.exec(
            select(Payment)
            .where(Payment.user_id == user.id)
            .where(Payment.market_id == market_id)
            .where(Payment.is_confirmed == True)
        ).first()
        if payment is not None:
            return True

        global_payment = session.exec(
            select(Payment)
            .where(Payment.user_id == user.id)
            .where(Payment.market_id == GLOBAL_PAYMENT_SCOPE)
            .where(Payment.is_confirmed == True)
        ).first()
        return global_payment is not None


def verify_x402_payment(proof: str, telegram_id: str, market_id: str | None) -> dict:
    normalized_proof = (proof or "").strip()
    normalized_telegram_id = str(telegram_id).strip()
    normalized_market_id = str(market_id).strip() if market_id else GLOBAL_PAYMENT_SCOPE

    if not normalized_proof:
        return {"verified": False, "reason": "Missing proof"}
    if not normalized_telegram_id:
        return {"verified": False, "reason": "Missing telegram_id"}
    if not _looks_like_valid_proof(normalized_proof):
        return {"verified": False, "reason": "Invalid proof format"}

    with Session(engine) as session:
        user = resolve_user_identity(normalized_telegram_id, session)
        if not user:
            if normalized_telegram_id.startswith("0x"):
                user = connect_wallet(
                    wallet_address=normalized_telegram_id.lower(),
                    session=session,
                )
            else:
                synthetic_wallet = f"telegram:{normalized_telegram_id}"
                user = connect_wallet(
                    wallet_address=synthetic_wallet,
                    session=session,
                    telegram_id=normalized_telegram_id,
                    username=f"telegram_{normalized_telegram_id}",
                )

        existing = session.exec(
            select(Payment).where(Payment.tx_hash == normalized_proof)
        ).first()
        if existing:
            if existing.user_id == user.id and existing.market_id == normalized_market_id and existing.is_confirmed:
                return {
                    "verified": True,
                    "market_id": normalized_market_id,
                    "tx_hash": normalized_proof,
                    "amount": existing.amount,
                    "asset": X402_ASSET,
                    "chain": X402_CHAIN,
                    "already_verified": True,
                }
            return {"verified": False, "reason": "Proof already used"}

        payment = Payment(
            user_id=user.id,
            market_id=normalized_market_id,
            amount=X402_REQUIRED_AMOUNT,
            tx_hash=normalized_proof,
            is_confirmed=True,
            timestamp=datetime.utcnow(),
        )
        session.add(payment)
        session.commit()

        return {
            "verified": True,
            "market_id": normalized_market_id,
            "tx_hash": normalized_proof,
            "amount": X402_REQUIRED_AMOUNT,
            "asset": X402_ASSET,
            "chain": X402_CHAIN,
            "already_verified": False,
        }


def _looks_like_valid_proof(proof: str) -> bool:
    if proof.startswith("0x") and len(proof) == 66:
        hex_part = proof[2:]
        return all(ch in "0123456789abcdefABCDEF" for ch in hex_part)
    return len(proof) >= 12


def resolve_user_identity(identity: str, session: Session) -> User | None:
    normalized = (identity or "").strip()
    if not normalized:
        return None

    user = get_user_by_telegram(normalized, session)
    if user:
        return user

    if normalized.startswith("0x"):
        return get_user_by_wallet(normalized.lower(), session)

    return None
