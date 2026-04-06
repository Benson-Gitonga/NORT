"""
Pretium Service — business logic for on-ramp / off-ramp flows.

Orchestrates: validation -> DB write -> Pretium API call -> DB update -> return.
Handles status mapping, balance crediting, webhook processing.

This layer sits between the API routes (controller) and the HTTP client (adapter).
"""

import logging
import os
import re
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from sqlmodel import Session, select

from services.backend.core.pretium_client import (
    PretiumClient,
    PretiumError,
    get_pretium_client,
)
from services.backend.data.models import PretiumTransaction, WalletConfig

logger = logging.getLogger("pretium.service")


# ─── Constants ───────────────────────────────────────────────────────────────

KENYA_PHONE_RE = re.compile(r"^\+254[17]\d{8}$")

TERMINAL_STATUSES = {"completed", "failed", "canceled", "refunded"}

# Status ordering for idempotent webhook handling (higher = later in lifecycle)
STATUS_ORDER = {
    "pending": 0,
    "processing": 1,
    "awaiting_payment": 2,
    "payment_confirmed": 3,
    "releasing_asset": 4,
    "completed": 5,
    "failed": 5,
    "canceled": 5,
    "refunded": 5,
}

DEFAULT_CHAIN = os.getenv("PRETIUM_CHAIN", "BASE")
DEFAULT_ASSET = os.getenv("PRETIUM_ASSET", "USDC")
DEFAULT_FIAT = os.getenv("PRETIUM_FIAT_CURRENCY", "KES")
DEFAULT_MOBILE_NETWORK = os.getenv("PRETIUM_MOBILE_NETWORK", "Safaricom")
WEBHOOK_BASE_URL = os.getenv("PRETIUM_WEBHOOK_BASE_URL", "")


# ─── Phone helpers ───────────────────────────────────────────────────────────

def normalize_phone(phone: str) -> str:
    """Normalize to +254XXXXXXXXX (E.164). Raises ValueError on invalid."""
    phone = phone.strip().replace(" ", "").replace("-", "")
    if phone.startswith("0"):
        phone = "+254" + phone[1:]
    elif phone.startswith("254") and not phone.startswith("+"):
        phone = "+" + phone
    if not KENYA_PHONE_RE.match(phone):
        raise ValueError(f"Invalid Kenyan phone number: {phone}")
    return phone


def phone_for_pretium(phone: str) -> str:
    """Pretium expects local format 07XXXXXXXX (shortcode)."""
    normalized = normalize_phone(phone)
    # Convert +254XXXXXXXXX -> 0XXXXXXXXX
    return "0" + normalized[4:]


# ─── Wallet helpers ──────────────────────────────────────────────────────────

def _ensure_wallet_config(tid: str, session: Session) -> WalletConfig:
    """Get or create WalletConfig for a user."""
    cfg = session.exec(
        select(WalletConfig).where(WalletConfig.telegram_user_id == tid)
    ).first()
    if not cfg:
        cfg = WalletConfig(telegram_user_id=tid)
        session.add(cfg)
        session.commit()
        session.refresh(cfg)
    return cfg


# ─── Exchange Rate ──────────────────────────────────────────────────────────

async def get_exchange_rate(
    currency_code: str = DEFAULT_FIAT,
    client: Optional[PretiumClient] = None,
) -> dict:
    """Get current exchange rates from Pretium."""
    client = client or get_pretium_client()
    raw = await client.get_exchange_rate(currency_code)
    data = raw.get("data", raw)
    return {
        "buying_rate": data.get("buying_rate"),
        "selling_rate": data.get("selling_rate"),
        "quoted_rate": data.get("quoted_rate"),
        "currency": currency_code,
    }


# ─── On-Ramp ────────────────────────────────────────────────────────────────

async def create_onramp(
    telegram_user_id: str,
    amount: int,
    phone_number: str,
    wallet_address: str,
    mobile_network: str = DEFAULT_MOBILE_NETWORK,
    chain: str = DEFAULT_CHAIN,
    asset: str = DEFAULT_ASSET,
    currency_code: str = DEFAULT_FIAT,
    fee: int = 0,
    session: Session = None,
    client: Optional[PretiumClient] = None,
) -> dict:
    """
    Create an on-ramp order: KES -> USDC.

    1. Validate inputs
    2. Get exchange rate for estimate
    3. Create DB record
    4. Call Pretium onramp (triggers STK push automatically)
    5. Return transaction details
    """
    client = client or get_pretium_client()
    phone = normalize_phone(phone_number)
    shortcode = phone_for_pretium(phone_number)

    tx_id = str(uuid.uuid4())

    # Get exchange rate for estimated crypto amount
    try:
        rates = await get_exchange_rate(currency_code, client)
        buying_rate = rates.get("buying_rate")
        estimated_crypto = round(amount / buying_rate, 2) if buying_rate else None
    except Exception:
        buying_rate = None
        estimated_crypto = None

    callback_url = f"{WEBHOOK_BASE_URL}/api/pretium/webhook"

    # Create DB record
    tx = PretiumTransaction(
        id=tx_id,
        telegram_user_id=telegram_user_id,
        type="onramp",
        amount_fiat=float(amount),
        amount_crypto=estimated_crypto,
        currency_code=currency_code,
        chain=chain,
        asset=asset,
        mobile_network=mobile_network,
        phone_number=phone,
        wallet_address=wallet_address,
        exchange_rate=buying_rate,
        fee=float(fee),
        status="pending",
    )
    session.add(tx)
    session.commit()

    # Call Pretium
    try:
        result = await client.create_onramp(
            shortcode=shortcode,
            amount=amount,
            mobile_network=mobile_network,
            chain=chain,
            asset=asset,
            address=wallet_address,
            callback_url=callback_url,
            fee=fee,
            currency_code=currency_code,
        )
    except PretiumError as e:
        tx.status = "failed"
        tx.error_message = e.message
        tx.updated_at = datetime.utcnow()
        session.add(tx)
        session.commit()
        raise

    # Update DB with Pretium response
    data = result.get("data", result)
    tx.pretium_transaction_code = data.get("transaction_code")
    tx.status = "processing"
    tx.updated_at = datetime.utcnow()
    session.add(tx)
    session.commit()

    logger.info("pretium.onramp.created", extra={
        "transaction_id": tx_id,
        "user_id": telegram_user_id,
        "amount_fiat": amount,
        "pretium_code": tx.pretium_transaction_code,
    })

    session.refresh(tx)

    return {
        "transaction_id": tx.id,
        "pretium_transaction_code": tx.pretium_transaction_code,
        "status": tx.status,
        "type": "onramp",
        "amount_fiat": tx.amount_fiat,
        "amount_crypto": tx.amount_crypto,
        "exchange_rate": tx.exchange_rate,
        "fee": tx.fee,
        "message": "STK push sent to your phone. Enter your M-Pesa PIN to complete.",
    }


# ─── Off-Ramp ───────────────────────────────────────────────────────────────

async def create_offramp(
    telegram_user_id: str,
    amount_crypto: float,
    phone_number: str,
    wallet_address: str,
    transaction_hash: str,
    mobile_network: str = DEFAULT_MOBILE_NETWORK,
    chain: str = DEFAULT_CHAIN,
    asset: str = DEFAULT_ASSET,
    currency_code: str = DEFAULT_FIAT,
    fee: int = 0,
    session: Session = None,
    client: Optional[PretiumClient] = None,
) -> dict:
    """
    Create an off-ramp order: USDC -> KES.

    Requires the user to have already sent crypto to the settlement wallet.
    The transaction_hash proves the on-chain transfer.

    1. Validate inputs
    2. Check USDC balance
    3. Get exchange rate for fiat estimate
    4. Deduct USDC balance upfront
    5. Call Pretium pay endpoint
    6. Return transaction details
    """
    client = client or get_pretium_client()
    phone = normalize_phone(phone_number)
    shortcode = phone_for_pretium(phone_number)
    tx_id = str(uuid.uuid4())

    # Check real USDC balance
    wallet_cfg = _ensure_wallet_config(telegram_user_id, session)
    if wallet_cfg.real_balance_usdc < amount_crypto:
        raise ValueError(
            f"Insufficient USDC balance: {wallet_cfg.real_balance_usdc:.2f} < {amount_crypto:.2f}"
        )

    # Get exchange rate for fiat estimate
    try:
        rates = await get_exchange_rate(currency_code, client)
        selling_rate = rates.get("selling_rate")
        estimated_fiat = round(amount_crypto * selling_rate) if selling_rate else 0
    except Exception:
        selling_rate = None
        estimated_fiat = 0

    callback_url = f"{WEBHOOK_BASE_URL}/api/pretium/webhook"

    # Debit USDC upfront
    wallet_cfg.real_balance_usdc -= amount_crypto
    wallet_cfg.updated_at = datetime.utcnow()

    tx = PretiumTransaction(
        id=tx_id,
        telegram_user_id=telegram_user_id,
        type="offramp",
        amount_fiat=float(estimated_fiat),
        amount_crypto=amount_crypto,
        currency_code=currency_code,
        chain=chain,
        asset=asset,
        mobile_network=mobile_network,
        phone_number=phone,
        wallet_address=wallet_address,
        exchange_rate=selling_rate,
        fee=float(fee),
        tx_hash=transaction_hash,
        status="pending",
    )
    session.add(tx)
    session.add(wallet_cfg)
    session.commit()

    # Call Pretium
    try:
        result = await client.create_offramp(
            shortcode=shortcode,
            amount=estimated_fiat,
            mobile_network=mobile_network,
            chain=chain,
            transaction_hash=transaction_hash,
            callback_url=callback_url,
            fee=fee,
            currency_code=currency_code,
        )
    except PretiumError as e:
        # Refund on failure
        wallet_cfg.real_balance_usdc += amount_crypto
        wallet_cfg.updated_at = datetime.utcnow()
        tx.status = "failed"
        tx.error_message = e.message
        tx.updated_at = datetime.utcnow()
        session.add(wallet_cfg)
        session.add(tx)
        session.commit()
        raise

    data = result.get("data", result)
    tx.pretium_transaction_code = data.get("transaction_code")
    tx.status = "processing"
    tx.updated_at = datetime.utcnow()
    session.add(tx)
    session.commit()

    logger.info("pretium.offramp.created", extra={
        "transaction_id": tx_id,
        "user_id": telegram_user_id,
        "amount_crypto": amount_crypto,
        "pretium_code": tx.pretium_transaction_code,
    })

    session.refresh(tx)

    return {
        "transaction_id": tx.id,
        "pretium_transaction_code": tx.pretium_transaction_code,
        "status": tx.status,
        "type": "offramp",
        "amount_crypto": tx.amount_crypto,
        "amount_fiat": tx.amount_fiat,
        "exchange_rate": tx.exchange_rate,
        "fee": tx.fee,
    }


# ─── Transaction queries ────────────────────────────────────────────────────

def get_transaction(transaction_id: str, session: Session) -> Optional[dict]:
    """Get a transaction by our ID."""
    tx = session.get(PretiumTransaction, transaction_id)
    if not tx:
        return None
    return _tx_to_dict(tx)


def list_transactions(
    telegram_user_id: str,
    tx_type: Optional[str] = None,
    limit: int = 20,
    session: Session = None,
) -> list:
    """List transactions for a user."""
    q = select(PretiumTransaction).where(
        PretiumTransaction.telegram_user_id == telegram_user_id
    )
    if tx_type:
        q = q.where(PretiumTransaction.type == tx_type)
    q = q.order_by(PretiumTransaction.created_at.desc()).limit(limit)

    txs = session.exec(q).all()
    return [_tx_to_dict(tx) for tx in txs]


async def check_transaction_status(
    transaction_id: str,
    session: Session,
    client: Optional[PretiumClient] = None,
) -> dict:
    """
    Check status of a transaction via Pretium API and update DB.

    Status response includes:
      status, amount, amount_in_usd, receipt_number, is_released,
      transaction_hash, category (DISBURSEMENT | COLLECTION), etc.
    """
    client = client or get_pretium_client()
    tx = session.get(PretiumTransaction, transaction_id)
    if not tx:
        raise ValueError(f"Transaction {transaction_id} not found")
    if not tx.pretium_transaction_code:
        return _tx_to_dict(tx)
    if tx.status in TERMINAL_STATUSES:
        return _tx_to_dict(tx)

    try:
        result = await client.get_transaction_status(
            tx.pretium_transaction_code, tx.currency_code
        )
        data = result.get("data", result)
        remote_status = data.get("status", "").upper()

        if data.get("receipt_number"):
            tx.receipt_number = data["receipt_number"]
        if data.get("transaction_hash") and not tx.tx_hash:
            tx.tx_hash = data["transaction_hash"]

        # Update actual amounts from Pretium if available
        amount_in_usd = data.get("amount_in_usd")
        if amount_in_usd:
            try:
                tx.amount_crypto = float(amount_in_usd)
            except (ValueError, TypeError):
                pass

        if remote_status == "COMPLETE":
            if tx.type == "offramp" and tx.status != "completed":
                # Off-ramp: COMPLETE = done
                tx.status = "completed"
                tx.completed_at = datetime.utcnow()

            elif tx.type == "onramp":
                is_released = data.get("is_released", False)
                if is_released and tx.status != "completed":
                    # On-ramp: only fully complete when asset is released
                    tx.status = "completed"
                    tx.completed_at = datetime.utcnow()

                    if tx.amount_crypto:
                        wallet_cfg = _ensure_wallet_config(tx.telegram_user_id, session)
                        wallet_cfg.real_balance_usdc += tx.amount_crypto
                        wallet_cfg.updated_at = datetime.utcnow()
                        session.add(wallet_cfg)
                elif not is_released and tx.status not in ("payment_confirmed", "completed"):
                    tx.status = "payment_confirmed"

        tx.updated_at = datetime.utcnow()
        session.add(tx)
        session.commit()
    except PretiumError:
        logger.warning("pretium.status_check.failed", extra={"transaction_id": transaction_id})

    session.refresh(tx)
    return _tx_to_dict(tx)


def _tx_to_dict(tx: PretiumTransaction) -> dict:
    return {
        "transaction_id": tx.id,
        "type": tx.type,
        "status": tx.status,
        "amount_fiat": tx.amount_fiat,
        "amount_crypto": tx.amount_crypto,
        "currency_code": tx.currency_code,
        "chain": tx.chain,
        "asset": tx.asset,
        "mobile_network": tx.mobile_network,
        "exchange_rate": tx.exchange_rate,
        "fee": tx.fee,
        "phone_number": tx.phone_number,
        "wallet_address": tx.wallet_address,
        "pretium_transaction_code": tx.pretium_transaction_code,
        "receipt_number": tx.receipt_number,
        "tx_hash": tx.tx_hash,
        "error_message": tx.error_message,
        "created_at": tx.created_at.isoformat() if tx.created_at else None,
        "updated_at": tx.updated_at.isoformat() if tx.updated_at else None,
        "completed_at": tx.completed_at.isoformat() if tx.completed_at else None,
    }


# ─── Webhook processing ─────────────────────────────────────────────────────

async def process_webhook(
    data: dict,
    session: Session,
) -> dict:
    """
    Process a Pretium webhook event.

    Pretium sends:
    - Offramp: single webhook on completion {status, transaction_code, receipt_number, ...}
    - Onramp: two webhooks:
      1. Payment confirmation {status: "COMPLETE", transaction_code, receipt_number, ...}
      2. Asset release {is_released: true/false, transaction_code, transaction_hash}
    """
    transaction_code = data.get("transaction_code")
    if not transaction_code:
        logger.warning("pretium.webhook.missing_transaction_code", extra={"data": data})
        return {"processed": False, "reason": "missing transaction_code"}

    # Find transaction
    tx = session.exec(
        select(PretiumTransaction).where(
            PretiumTransaction.pretium_transaction_code == transaction_code
        )
    ).first()

    if not tx:
        logger.warning("pretium.webhook.tx_not_found", extra={"transaction_code": transaction_code})
        return {"processed": False, "reason": "transaction not found"}

    # Handle asset release webhook (onramp second notification)
    if "is_released" in data:
        is_released = data.get("is_released", False)
        tx_hash = data.get("transaction_hash")

        if is_released and tx_hash:
            tx.tx_hash = tx_hash
            tx.status = "completed"
            tx.completed_at = datetime.utcnow()
            tx.updated_at = datetime.utcnow()

            # Credit USDC balance for on-ramp
            if tx.type == "onramp" and tx.amount_crypto:
                wallet_cfg = _ensure_wallet_config(tx.telegram_user_id, session)
                wallet_cfg.real_balance_usdc += tx.amount_crypto
                wallet_cfg.updated_at = datetime.utcnow()
                session.add(wallet_cfg)
                logger.info("pretium.onramp.balance_credited", extra={
                    "transaction_id": tx.id,
                    "usdc_credited": tx.amount_crypto,
                })

            session.add(tx)
            session.commit()
            return {"processed": True, "transaction_id": tx.id, "status": "completed"}

        return {"processed": True, "transaction_id": tx.id, "status": tx.status}

    # Handle payment confirmation / completion webhook
    status = data.get("status", "").upper()
    receipt_number = data.get("receipt_number")

    if receipt_number:
        tx.receipt_number = receipt_number

    if status == "COMPLETE":
        if tx.type == "offramp":
            # Off-ramp: single webhook = fully done
            tx.status = "completed"
            tx.completed_at = datetime.utcnow()
            logger.info("pretium.offramp.completed", extra={
                "transaction_id": tx.id,
                "user_id": tx.telegram_user_id,
            })
        elif tx.type == "onramp":
            # On-ramp: first webhook = payment confirmed, waiting for asset release
            tx.status = "payment_confirmed"
            logger.info("pretium.onramp.payment_confirmed", extra={
                "transaction_id": tx.id,
            })
    elif status in ("FAILED", "CANCELLED"):
        tx.status = "failed"
        tx.error_message = data.get("message", "Transaction failed")

        # Refund USDC for failed off-ramp
        if tx.type == "offramp" and tx.amount_crypto:
            wallet_cfg = _ensure_wallet_config(tx.telegram_user_id, session)
            wallet_cfg.real_balance_usdc += tx.amount_crypto
            wallet_cfg.updated_at = datetime.utcnow()
            session.add(wallet_cfg)
            logger.info("pretium.offramp.balance_refunded", extra={
                "transaction_id": tx.id,
                "usdc_refunded": tx.amount_crypto,
            })

    tx.updated_at = datetime.utcnow()
    session.add(tx)
    session.commit()

    logger.info("pretium.webhook.processed", extra={
        "transaction_id": tx.id,
        "status": tx.status,
    })

    return {"processed": True, "transaction_id": tx.id, "status": tx.status}


# ─── Settlement info ─────────────────────────────────────────────────────────

async def get_settlement_address(
    chain: str = DEFAULT_CHAIN,
    client: Optional[PretiumClient] = None,
) -> Optional[str]:
    """Get the settlement wallet address for a given chain from account details."""
    client = client or get_pretium_client()
    try:
        details = await client.get_account_details()
        data = details.get("data", details)
        networks = data.get("networks", [])
        for network in networks:
            if network.get("name", "").upper() == chain.upper():
                return network.get("settlement_wallet_address")
    except PretiumError:
        logger.warning("pretium.settlement_address.failed", extra={"chain": chain})
    return None
