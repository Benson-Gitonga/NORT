import os
import httpx
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(override=False)  # safe — won't override values already in os.environ


from sqlmodel import Session, select

from services.backend.core.paper_trading import connect_wallet, get_user_by_telegram, get_user_by_wallet
from services.backend.data.database import engine
from services.backend.data.models import Payment, User

X402_REQUIRED_AMOUNT = float(os.getenv("X402_REQUIRED_AMOUNT", "1.00"))
X402_ASSET = os.getenv("X402_ASSET", "USDC")
X402_CHAIN = os.getenv("X402_CHAIN", "Base")
X402_TREASURY_ADDRESS = os.getenv("NORT_TREASURY_ADDRESS", "").strip().lower()
GLOBAL_PAYMENT_SCOPE = "__global__"

# ── Base chain constants ────────────────────────────────────────────────────
BASE_RPC_URL = "https://mainnet.base.org"
BASE_USDC_CONTRACT = "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913"  # USDC on Base
ERC20_TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
USDC_DECIMALS = 6


def payment_required_payload(market_id: str) -> dict:
    return {
        "message": "Payment required",
        "market_id": market_id,
        "amount": X402_REQUIRED_AMOUNT,
        "asset": X402_ASSET,
        "chain": X402_CHAIN,
        "address": X402_TREASURY_ADDRESS,
    }


async def verify_onchain_usdc_transfer(
    tx_hash: str,
    treasury: str,
    min_amount_usdc: float,
) -> dict:
    """
    Verify a real USDC transfer on Base mainnet (async — non-blocking).
    Parses the ERC-20 Transfer event log to confirm:
      - The tx succeeded (status == 0x1)
      - The recipient (topics[2]) matches the treasury
      - The amount (data) is >= min_amount_usdc
    Returns {"ok": True, "amount_usdc": x} or {"ok": False, "reason": "..."}
    """
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(BASE_RPC_URL, json={
                "jsonrpc": "2.0",
                "method": "eth_getTransactionReceipt",
                "params": [tx_hash],
                "id": 1,
            })
        receipt = r.json().get("result")
    except Exception as e:
        return {"ok": False, "reason": f"Base RPC error: {e}"}

    if not receipt:
        return {"ok": False, "reason": "Transaction not found on-chain — it may still be pending."}
    if receipt.get("status") != "0x1":
        return {"ok": False, "reason": "Transaction failed on-chain (status != 0x1)."}

    treasury_normalized = treasury.lower().replace("0x", "").zfill(64)
    min_raw = int(min_amount_usdc * (10 ** USDC_DECIMALS))

    for log in receipt.get("logs", []):
        # Must be emitted by the USDC contract
        if log.get("address", "").lower() != BASE_USDC_CONTRACT:
            continue
        topics = log.get("topics", [])
        if len(topics) < 3:
            continue
        # topics[0] = Transfer event keccak256 signature
        if topics[0].lower() != ERC20_TRANSFER_TOPIC:
            continue
        # topics[2] = recipient address (zero-padded to 32 bytes)
        to_padded = topics[2].lower().replace("0x", "").zfill(64)
        if to_padded != treasury_normalized:
            continue
        # data = uint256 amount transferred
        raw_data = log.get("data", "0x0")
        raw_amount = int(raw_data, 16)
        if raw_amount >= min_raw:
            return {"ok": True, "amount_usdc": raw_amount / (10 ** USDC_DECIMALS)}

    return {
        "ok": False,
        "reason": (
            f"No USDC Transfer of ≥ ${min_amount_usdc:.2f} to treasury found. "
            "Please ensure you sent USDC (not ETH) on Base chain to the correct address."
        ),
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


def has_any_confirmed_payment(telegram_id: str | None) -> bool:
    if not telegram_id:
        return False

    with Session(engine) as session:
        user = resolve_user_identity(str(telegram_id), session)
        if not user:
            return False

        payment = session.exec(
            select(Payment)
            .where(Payment.user_id == user.id)
            .where(Payment.is_confirmed == True)
        ).first()
        return payment is not None


async def verify_x402_payment(proof: str, telegram_id: str, market_id: str | None) -> dict:
    normalized_proof = (proof or "").strip()
    normalized_telegram_id = str(telegram_id).strip()
    normalized_market_id = str(market_id).strip() if market_id else GLOBAL_PAYMENT_SCOPE

    if not normalized_proof:
        return {"verified": False, "reason": "Missing proof"}
    if not normalized_telegram_id:
        return {"verified": False, "reason": "Missing telegram_id"}

    # ── DEMO BYPASS ────────────────────────────────────────────────────────────
    # Typing "demo" instantly grants Premium for demonstration purposes.
    # This lets you showcase the Free → Premium flow without a real payment.
    if normalized_proof.lower() == "demo":
        # Demo payments are stored against GLOBAL_PAYMENT_SCOPE so one demo
        # unlock covers every market — consistent with has_any_confirmed_payment.
        demo_scope = GLOBAL_PAYMENT_SCOPE
        with Session(engine) as session:
            user = resolve_user_identity(normalized_telegram_id, session)
            if not user:
                if normalized_telegram_id.startswith("0x"):
                    user = connect_wallet(wallet_address=normalized_telegram_id.lower(), session=session)
                else:
                    synthetic_wallet = f"telegram:{normalized_telegram_id}"
                    user = connect_wallet(
                        wallet_address=synthetic_wallet,
                        session=session,
                        telegram_id=normalized_telegram_id,
                        username=f"telegram_{normalized_telegram_id}",
                    )
            # If resolve found a synthetic duplicate, prefer the canonical wallet user
            # (e.g. wallet=0x... exists as id=1, but demo created telegram:0x... as id=2)
            if normalized_telegram_id.startswith("0x"):
                canonical = session.exec(
                    select(User).where(User.wallet_address == normalized_telegram_id.lower())
                ).first()
                if canonical:
                    user = canonical
            demo_hash = f"demo_{normalized_telegram_id}_{demo_scope}"
            existing = session.exec(
                select(Payment).where(Payment.tx_hash == demo_hash)
            ).first()
            if not existing:
                payment = Payment(
                    user_id=user.id,
                    market_id=demo_scope,
                    amount=X402_REQUIRED_AMOUNT,
                    tx_hash=demo_hash,
                    is_confirmed=True,
                    timestamp=datetime.utcnow(),
                )
                session.add(payment)
                session.commit()
        return {
            "verified": True,
            "market_id": demo_scope,
            "tx_hash": demo_hash,
            "amount": X402_REQUIRED_AMOUNT,
            "asset": X402_ASSET,
            "chain": X402_CHAIN,
            "already_verified": existing is not None,
            "demo": True,
        }
    # ── END DEMO BYPASS ────────────────────────────────────────────────────────

    if not _looks_like_valid_proof(normalized_proof):
        return {"verified": False, "reason": "Invalid proof format — expected a 0x transaction hash (0x + 64 hex chars)."}

    # ── REAL ON-CHAIN VERIFICATION ────────────────────────────────────────────
    # Check the Base blockchain for a USDC Transfer log to our treasury.
    if X402_TREASURY_ADDRESS:
        onchain = await verify_onchain_usdc_transfer(
            tx_hash=normalized_proof,
            treasury=X402_TREASURY_ADDRESS,
            min_amount_usdc=X402_REQUIRED_AMOUNT,
        )
        if not onchain["ok"]:
            return {"verified": False, "reason": onchain["reason"]}
    # If treasury not configured, fall through (dev/staging only)

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
    """
    Accept only real on-chain transaction hashes: 0x + 64 hex chars.
    Reject anything else to prevent arbitrary strings from creating
    confirmed payment records in the database.
    """
    if not proof.startswith("0x") or len(proof) != 66:
        return False
    hex_part = proof[2:]
    return all(ch in "0123456789abcdefABCDEF" for ch in hex_part)


def resolve_user_identity(identity: str, session: Session) -> User | None:
    normalized = (identity or "").strip()
    if not normalized:
        return None

    # Handle "tg_" prefix from the dashboard/web-auth layer
    tg_id = normalized.removeprefix("tg_")
    user = get_user_by_telegram(tg_id, session)
    if user:
        return user

    # Canonical wallet address — always prefer this over synthetic telegram: rows
    if normalized.startswith("0x"):
        canonical = get_user_by_wallet(normalized.lower(), session)
        if canonical:
            return canonical
        # Some rows were created as wallet="telegram:0x..." — fall through below

    # Handle synthetic "telegram:0x..." wallets created by the old demo flow
    synthetic = get_user_by_wallet(f"telegram:{normalized.lower()}", session)
    if synthetic:
        return synthetic

    return None
