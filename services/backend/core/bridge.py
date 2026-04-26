"""
LI.FI Bridge Service — Phase 2

Handles all cross-chain bridging from Base → Polygon (USDC).
Called exclusively from the backend. Never from the frontend.

Flow for a real trade:
  1. get_bridge_quote()     → get quote + transaction data from LI.FI
  2. (frontend signs + sends the tx using Privy)
  3. track_bridge()         → record tx hash in DB, start polling
  4. poll_bridge_status()   → poll LI.FI until status == DONE
  5. On DONE                → execute Polymarket trade via real_trading_engine

Rate limits:
  Unauthenticated: 200 req / 2hr
  With API key:    200 req / min  ← get key at portal.li.fi
"""

import asyncio
import httpx
import os
import logging
from datetime import datetime, timedelta
from typing import Optional
from sqlmodel import Session, select

from services.backend.data.models import BridgeTransaction, RealTrade

logger = logging.getLogger(__name__)

LIFI_API_URL = "https://li.quest/v1"
LIFI_API_KEY = os.getenv("LIFI_API_KEY", "")

USDC_BASE       = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
USDC_POLYGON    = "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"
BASE_CHAIN_ID    = 8453
POLYGON_CHAIN_ID = 137

_QUOTE_CACHE: dict = {}
QUOTE_CACHE_TTL = 30

_SEMAPHORE = asyncio.Semaphore(3)


def _headers() -> dict:
    h = {"Content-Type": "application/json"}
    if LIFI_API_KEY:
        h["x-lifi-api-key"] = LIFI_API_KEY
    return h


# ─── QUOTE ───────────────────────────────────────────────────────────────────

async def get_bridge_quote(from_wallet: str, to_wallet: str, amount_usdc: float) -> dict:
    amount_str = str(int(amount_usdc * 1_000_000))
    cache_key  = (from_wallet.lower(), amount_str)

    if cache_key in _QUOTE_CACHE:
        quote, expires_at = _QUOTE_CACHE[cache_key]
        if datetime.utcnow() < expires_at:
            return quote

    params = {
        "fromChain":   BASE_CHAIN_ID,
        "toChain":     POLYGON_CHAIN_ID,
        "fromToken":   USDC_BASE,
        "toToken":     USDC_POLYGON,
        "fromAmount":  amount_str,
        "fromAddress": from_wallet,
        "toAddress":   to_wallet,
        "slippage":    "0.005",
        "integrator":  "nort",
    }

    async with _SEMAPHORE:
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.get(f"{LIFI_API_URL}/quote", params=params, headers=_headers())
                resp.raise_for_status()
                quote = resp.json()
                _QUOTE_CACHE[cache_key] = (quote, datetime.utcnow() + timedelta(seconds=QUOTE_CACHE_TTL))
                logger.info(f"[lifi] Quote: {amount_usdc} USDC via {quote.get('tool','?')}")
                return quote
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    raise BridgeRateLimitError("LI.FI rate limit hit. Try again in a moment.")
                raise BridgeError(f"LI.FI quote failed: {e.response.status_code} {e.response.text[:200]}")
            except Exception as e:
                raise BridgeError(f"LI.FI quote error: {e}")


# ─── STATUS POLLING ──────────────────────────────────────────────────────────

async def get_bridge_status(tx_hash: str, from_chain: int = BASE_CHAIN_ID) -> dict:
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


# ─── BRIDGE COMPLETION → TRADE TRIGGER ──────────────────────────────────────

async def _trigger_trade_after_bridge(bridge: BridgeTransaction, session: Session) -> None:
    """
    Called when a bridge transaction reaches DONE status.

    If the bridge has a linked real_trade_id, that trade was waiting for USDC
    to arrive on Polygon before execution. Now that USDC is here, we fire the
    Polymarket CLOB order.

    This is the final link in the chain:
      Pretium (deposit) → bridge DONE → place_real_trade → CLOB order open
    """
    if not bridge.real_trade_id:
        return

    trade = session.get(RealTrade, bridge.real_trade_id)
    if not trade:
        logger.error(f"[bridge→trade] RealTrade {bridge.real_trade_id} not found")
        return

    # Only trigger if trade is still waiting for bridge
    if trade.status != "pending_bridge":
        logger.info(f"[bridge→trade] Trade {trade.id} already in status={trade.status}, skipping")
        return

    logger.info(f"[bridge→trade] Bridge {bridge.id} DONE → firing trade {trade.id}")

    # Update trade status to show bridge is done, execution pending
    trade.status           = "pending_execution"
    trade.bridged_amount_usdc = bridge.amount_usdc
    trade.updated_at       = datetime.utcnow()
    session.add(trade)
    session.commit()

    # Import here to avoid circular imports at module level
    from services.backend.core.real_trading_engine import place_real_trade, PolymarketError

    try:
        completed_trade = await place_real_trade(
            telegram_user_id=trade.telegram_user_id,
            wallet_address=trade.wallet_address,
            market_id=trade.market_id,
            market_question=trade.market_question,
            outcome=trade.outcome,
            amount_usdc=bridge.amount_usdc,
            session=session,
        )
        logger.info(
            f"[bridge→trade] Trade {completed_trade.id} now OPEN "
            f"order={completed_trade.polymarket_order_id}"
        )
    except Exception as e:
        logger.error(f"[bridge→trade] Trade execution failed after bridge: {e}")
        trade.status        = "failed"
        trade.error_message = f"Bridge completed but trade execution failed: {e}"
        trade.updated_at    = datetime.utcnow()
        session.add(trade)
        session.commit()


async def wait_for_bridge(
    tx_hash: str,
    session: Session,
    bridge_id: int,
    poll_interval: int = 15,
    timeout_seconds: int = 600,
) -> BridgeTransaction:
    """
    Poll LI.FI until the bridge is DONE, FAILED, or times out.
    On DONE: triggers real trade execution if the bridge is linked to a RealTrade.
    Runs as a FastAPI BackgroundTask — does not block the API response.
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
                _update_bridge(session, bridge_id, "done", receiving_tx_hash=receiving_tx)
                logger.info(f"[lifi] Bridge {bridge_id} DONE. Receiving tx: {receiving_tx}")

                # ── Wire: bridge complete → fire the real trade ──
                bridge_record = session.get(BridgeTransaction, bridge_id)
                if bridge_record:
                    await _trigger_trade_after_bridge(bridge_record, session)

                return session.get(BridgeTransaction, bridge_id)

            elif status_raw in ("FAILED", "INVALID"):
                error = result.get("substatusMessage", "Bridge failed.")
                _update_bridge(session, bridge_id, "failed", error=error)
                logger.warning(f"[lifi] Bridge {bridge_id} FAILED: {error}")

                # Refund user balance on bridge failure
                bridge_record = session.get(BridgeTransaction, bridge_id)
                if bridge_record:
                    _refund_on_bridge_failure(bridge_record, session)

                return session.get(BridgeTransaction, bridge_id)

            elif status_raw == "REFUNDED":
                _update_bridge(session, bridge_id, "refunded")
                logger.warning(f"[lifi] Bridge {bridge_id} REFUNDED by LI.FI.")

                bridge_record = session.get(BridgeTransaction, bridge_id)
                if bridge_record:
                    _refund_on_bridge_failure(bridge_record, session)

                return session.get(BridgeTransaction, bridge_id)

            else:
                new_status = "bridging" if status_raw == "PENDING" else status_raw.lower()
                if new_status != last_status:
                    _update_bridge(session, bridge_id, new_status)
                    last_status = new_status
                    logger.info(f"[lifi] Bridge {bridge_id}: {new_status} ({elapsed:.0f}s)")

        except BridgeRateLimitError:
            logger.warning(f"[lifi] Rate limited — backing off 60s")
            await asyncio.sleep(60)
        except BridgeError as e:
            logger.warning(f"[lifi] Poll error: {e} — retrying")


def _refund_on_bridge_failure(bridge: BridgeTransaction, session: Session) -> None:
    """
    If a bridge fails or is refunded and it was linked to a real trade,
    mark the trade as failed and credit the user's balance back.
    """
    if not bridge.real_trade_id:
        return

    trade = session.get(RealTrade, bridge.real_trade_id)
    if not trade or trade.status not in ("pending_bridge", "pending_execution"):
        return

    from services.backend.core.paper_trading import _ensure_wallet_config
    config = _ensure_wallet_config(trade.telegram_user_id, session)
    config.real_balance_usdc = round(config.real_balance_usdc + trade.total_cost_usdc, 6)
    config.updated_at = datetime.utcnow()
    trade.status = "failed"
    trade.error_message = "Bridge failed before trade could be executed — balance refunded."
    trade.updated_at = datetime.utcnow()
    session.add(config)
    session.add(trade)
    session.commit()
    logger.info(
        f"[bridge_refund] Trade {trade.id} refunded "
        f"${trade.total_cost_usdc} USDC to {trade.telegram_user_id[:10]}"
    )


# ─── DB HELPERS ──────────────────────────────────────────────────────────────

def create_bridge_record(
    session: Session,
    telegram_user_id: str,
    wallet_address: str,
    amount_usdc: float,
    real_trade_id: Optional[int] = None,
) -> BridgeTransaction:
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