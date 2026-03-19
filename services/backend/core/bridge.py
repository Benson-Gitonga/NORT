"""
LI.FI Bridge Service — Phase 2

Handles all cross-chain bridging from Base → Polygon (USDC).
Called exclusively from the backend. Never from the frontend.

Flow for a real trade:
  1. get_bridge_quote()        → get quote + transaction data from LI.FI
  2. (frontend signs + sends the tx using Privy)
  3. track_bridge()            → record tx hash in DB, start polling
  4. poll_bridge_status()      → poll LI.FI until status == DONE
  5. On DONE → execute Polymarket trade (Phase 4)

Rate limits:
  Unauthenticated: 200 req / 2hr
  With API key:    200 req / min  ← get key at portal.li.fi

Rate limit protection:
  - Quote cache: same wallet+amount cached for 30s
  - Status polling: max 1 req per bridge per 15s
  - Asyncio semaphore: max 3 concurrent LI.FI calls
"""

import asyncio
import httpx
import os
import logging
from datetime import datetime, timedelta
from typing import Optional
from sqlmodel import Session, select

from services.backend.data.models import BridgeTransaction

logger = logging.getLogger(__name__)

# ─── CONFIG ──────────────────────────────────────────────────────────────────

LIFI_API_URL    = "https://li.quest/v1"
LIFI_API_KEY    = os.getenv("LIFI_API_KEY", "")

# USDC contract addresses
USDC_BASE       = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"  # Base USDC
USDC_POLYGON    = "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"  # Polygon native USDC

# Chain IDs
BASE_CHAIN_ID    = 8453
POLYGON_CHAIN_ID = 137

# Quote cache: key = (wallet_address, amount_str) → (quote_data, expires_at)
_QUOTE_CACHE: dict = {}
QUOTE_CACHE_TTL = 30  # seconds

# Semaphore: max 3 concurrent LI.FI calls
_SEMAPHORE = asyncio.Semaphore(3)

# ─── HEADERS ─────────────────────────────────────────────────────────────────

def _headers() -> dict:
    h = {"Content-Type": "application/json"}
    if LIFI_API_KEY:
        h["x-lifi-api-key"] = LIFI_API_KEY
    return h


# ─── QUOTE ───────────────────────────────────────────────────────────────────

async def get_bridge_quote(
    from_wallet: str,
    to_wallet: str,
    amount_usdc: float,
) -> dict:
    """
    Get a bridge quote from Base USDC → Polygon USDC via LI.FI.

    Returns the full quote object including:
      - transactionRequest: the tx the user must sign and send
      - estimate: fees, gas, estimated duration
      - tool: which bridge will be used (e.g. "stargate", "across")

    Cached for 30 seconds per (wallet, amount) pair.
    """
    # Amount in USDC micro-units (6 decimals)
    amount_str = str(int(amount_usdc * 1_000_000))
    cache_key  = (from_wallet.lower(), amount_str)

    # Return cached quote if still fresh
    if cache_key in _QUOTE_CACHE:
        quote, expires_at = _QUOTE_CACHE[cache_key]
        if datetime.utcnow() < expires_at:
            logger.info(f"[lifi] Quote cache hit for {from_wallet} {amount_usdc} USDC")
            return quote

    params = {
        "fromChain":   BASE_CHAIN_ID,
        "toChain":     POLYGON_CHAIN_ID,
        "fromToken":   USDC_BASE,
        "toToken":     USDC_POLYGON,
        "fromAmount":  amount_str,
        "fromAddress": from_wallet,
        "toAddress":   to_wallet,
        "slippage":    "0.005",           # 0.5% slippage tolerance
        "integrator":  "nort",
    }

    async with _SEMAPHORE:
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.get(
                    f"{LIFI_API_URL}/quote",
                    params=params,
                    headers=_headers(),
                )
                resp.raise_for_status()
                quote = resp.json()

                # Cache it
                _QUOTE_CACHE[cache_key] = (
                    quote,
                    datetime.utcnow() + timedelta(seconds=QUOTE_CACHE_TTL)
                )
                logger.info(
                    f"[lifi] Quote: {amount_usdc} USDC Base→Polygon "
                    f"via {quote.get('tool', 'unknown')} "
                    f"est. {quote.get('estimate', {}).get('executionDuration', '?')}s"
                )
                return quote

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    raise BridgeRateLimitError("LI.FI rate limit hit. Try again in a moment.")
                raise BridgeError(f"LI.FI quote failed: {e.response.status_code} {e.response.text[:200]}")
            except Exception as e:
                raise BridgeError(f"LI.FI quote error: {e}")


# ─── STATUS POLLING ───────────────────────────────────────────────────────────

async def get_bridge_status(tx_hash: str, from_chain: int = BASE_CHAIN_ID) -> dict:
    """
    Poll LI.FI for the status of a submitted bridge transaction.

    Returns:
      status: PENDING | DONE | FAILED | INVALID | NOT_FOUND
      receiving: { txHash, chainId } when tokens arrive on Polygon
    """
    async with _SEMAPHORE:
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(
                    f"{LIFI_API_URL}/status",
                    params={"txHash": tx_hash, "fromChain": from_chain},
                    headers=_headers(),
                )
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    raise BridgeRateLimitError("LI.FI rate limit hit during status check.")
                raise BridgeError(f"LI.FI status check failed: {e.response.status_code}")
            except Exception as e:
                raise BridgeError(f"LI.FI status error: {e}")


async def wait_for_bridge(
    tx_hash: str,
    session: Session,
    bridge_id: int,
    poll_interval: int = 15,
    timeout_seconds: int = 600,  # 10 minute max wait
) -> BridgeTransaction:
    """
    Poll LI.FI status until the bridge is DONE, FAILED, or times out.
    Updates the BridgeTransaction record in DB on each status change.

    poll_interval: seconds between polls (15s default — rate-limit friendly)
    timeout_seconds: give up after this many seconds

    This runs as a background asyncio task — does NOT block the API response.
    """
    start = datetime.utcnow()
    last_status = "pending"

    while True:
        elapsed = (datetime.utcnow() - start).total_seconds()
        if elapsed > timeout_seconds:
            _update_bridge(session, bridge_id, "failed", error="Bridge timed out after 10 minutes.")
            logger.warning(f"[lifi] Bridge {bridge_id} timed out after {elapsed:.0f}s")
            return session.get(BridgeTransaction, bridge_id)

        await asyncio.sleep(poll_interval)

        try:
            result = await get_bridge_status(tx_hash)
            status_raw = result.get("status", "PENDING").upper()

            if status_raw == "DONE":
                receiving_tx = result.get("receiving", {}).get("txHash")
                _update_bridge(
                    session, bridge_id, "done",
                    receiving_tx_hash=receiving_tx,
                )
                logger.info(f"[lifi] Bridge {bridge_id} DONE. Receiving tx: {receiving_tx}")
                return session.get(BridgeTransaction, bridge_id)

            elif status_raw in ("FAILED", "INVALID"):
                error = result.get("substatusMessage", "Bridge failed.")
                _update_bridge(session, bridge_id, "failed", error=error)
                logger.warning(f"[lifi] Bridge {bridge_id} FAILED: {error}")
                return session.get(BridgeTransaction, bridge_id)

            elif status_raw == "REFUNDED":
                _update_bridge(session, bridge_id, "refunded")
                logger.warning(f"[lifi] Bridge {bridge_id} REFUNDED by LI.FI.")
                return session.get(BridgeTransaction, bridge_id)

            else:
                # Still pending/bridging — update status if changed
                new_status = "bridging" if status_raw == "PENDING" else status_raw.lower()
                if new_status != last_status:
                    _update_bridge(session, bridge_id, new_status)
                    last_status = new_status
                    logger.info(f"[lifi] Bridge {bridge_id} status: {new_status} ({elapsed:.0f}s)")

        except BridgeRateLimitError:
            # Back off for 60s if rate limited
            logger.warning(f"[lifi] Rate limited during bridge poll — backing off 60s")
            await asyncio.sleep(60)

        except BridgeError as e:
            logger.warning(f"[lifi] Bridge poll error: {e} — retrying")


# ─── DB HELPERS ──────────────────────────────────────────────────────────────

def create_bridge_record(
    session: Session,
    telegram_user_id: str,
    wallet_address: str,
    amount_usdc: float,
    real_trade_id: Optional[int] = None,
) -> BridgeTransaction:
    """Create a BridgeTransaction record before submitting the tx."""
    bridge = BridgeTransaction(
        telegram_user_id=telegram_user_id,
        wallet_address=wallet_address.lower(),
        amount_usdc=amount_usdc,
        status="pending",
        real_trade_id=real_trade_id,
    )
    session.add(bridge)
    session.commit()
    session.refresh(bridge)
    return bridge


def record_bridge_tx_hash(session: Session, bridge_id: int, tx_hash: str) -> None:
    """Called after the user signs and submits the bridge tx."""
    bridge = session.get(BridgeTransaction, bridge_id)
    if bridge:
        bridge.lifi_tx_hash = tx_hash
        bridge.status       = "bridging"
        bridge.updated_at   = datetime.utcnow()
        session.add(bridge)
        session.commit()


def _update_bridge(
    session: Session,
    bridge_id: int,
    status: str,
    receiving_tx_hash: Optional[str] = None,
    error: Optional[str] = None,
) -> None:
    bridge = session.get(BridgeTransaction, bridge_id)
    if not bridge:
        return
    bridge.status     = status
    bridge.updated_at = datetime.utcnow()
    if receiving_tx_hash:
        bridge.lifi_receiving_tx_hash = receiving_tx_hash
    if error:
        bridge.error_message = error
    if status in ("done", "failed", "refunded"):
        bridge.completed_at = datetime.utcnow()
    session.add(bridge)
    session.commit()


# ─── ERRORS ──────────────────────────────────────────────────────────────────

class BridgeError(Exception):
    pass

class BridgeRateLimitError(BridgeError):
    pass
