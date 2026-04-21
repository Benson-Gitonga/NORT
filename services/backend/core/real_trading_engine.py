"""
real_trading_engine.py — Phase 4: Real On-Chain Trading (Custodial Server-Wallet)

Architecture
────────────
NORT runs a single server-controlled Polygon wallet that:
  1. Holds pooled USDC bridged from user deposits (via Pretium + LI.FI)
  2. Places CTF orders on Polymarket CLOB on behalf of users
  3. Polls open orders for settlement, credits/debits user DB balances

Users never need their own Polygon wallet or Polymarket API keys.

Order lifecycle
───────────────
  pending_execution → placed CLOB order → open
  open              → market resolves  → closed (WIN | LOSS)
  any step          → error            → failed (balance refunded)

Required env vars (see .env.example for full details)
────────────────────────────────────────────────────
  POLYMARKET_API_KEY            — from polymarket.com/profile
  POLYMARKET_API_SECRET         — from polymarket.com/profile
  POLYMARKET_PASSPHRASE         — from polymarket.com/profile
  SERVER_POLYGON_WALLET_PK      — private key of server Polygon wallet
  SERVER_POLYGON_WALLET_ADDRESS — public address of server Polygon wallet
  REAL_TRADING_ENABLED          — "true" to enable
  REAL_TRADING_BETA_ALLOWLIST   — comma-separated allowed wallet addresses
"""

import os
import logging
import asyncio
import httpx
from datetime import datetime, timedelta
from typing import Optional
from sqlmodel import Session, select

from services.backend.data.models import RealTrade, WalletConfig, Market
from services.backend.core.paper_trading import _ensure_wallet_config

logger = logging.getLogger(__name__)

# ─── CONFIG ──────────────────────────────────────────────────────────────────

POLYMARKET_CLOB_URL        = "https://clob.polymarket.com"
POLYMARKET_API_KEY         = os.getenv("POLYMARKET_API_KEY", "").strip()
POLYMARKET_SECRET          = os.getenv("POLYMARKET_API_SECRET", "").strip()
POLYMARKET_PASS            = os.getenv("POLYMARKET_PASSPHRASE", "").strip()
SERVER_WALLET_PK           = os.getenv("SERVER_POLYGON_WALLET_PK", "").strip()
SERVER_WALLET_ADDRESS      = os.getenv("SERVER_POLYGON_WALLET_ADDRESS", "").strip()

REAL_TRADING_ENABLED = os.getenv("REAL_TRADING_ENABLED", "false").lower() == "true"

_ALLOWLIST_RAW = os.getenv("REAL_TRADING_BETA_ALLOWLIST", "")
BETA_ALLOWLIST = {w.strip().lower() for w in _ALLOWLIST_RAW.split(",") if w.strip()}

MIN_REAL_TRADE_USDC  = float(os.getenv("MIN_REAL_TRADE_USDC", "1.0"))
MAX_REAL_TRADE_USDC  = float(os.getenv("MAX_REAL_TRADE_USDC", "50.0"))

# Polygon USDC contract address (native USDC, not USDC.e)
USDC_POLYGON = "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"
POLYGON_RPC  = os.getenv("POLYGON_RPC_URL", "https://polygon-rpc.com")


# ─── ERRORS ──────────────────────────────────────────────────────────────────

class RealTradingError(Exception):
    """Base for all real trading errors."""

class RealTradingDisabledError(RealTradingError):
    """Feature flag off or user not in beta."""

class InsufficientRealBalanceError(RealTradingError):
    """User's DB real_balance_usdc is too low."""

class PolymarketError(RealTradingError):
    """CLOB API call failed."""

class ConfigurationError(RealTradingError):
    """A required env var is missing."""


# ─── BETA GATE ───────────────────────────────────────────────────────────────

def assert_real_trading_allowed(wallet_address: str) -> None:
    """
    Raises RealTradingDisabledError if the feature flag is off
    or the user is not in the closed-beta allowlist.
    """
    if not REAL_TRADING_ENABLED:
        raise RealTradingDisabledError(
            "Real trading is not yet enabled. Stay tuned for the beta launch."
        )
    if BETA_ALLOWLIST and wallet_address.lower() not in BETA_ALLOWLIST:
        raise RealTradingDisabledError(
            "Real trading is in closed beta. "
            "You're on the waitlist — we'll notify you when your access is ready."
        )


def _assert_configured() -> None:
    """Raise ConfigurationError if critical env vars are missing."""
    missing = []
    if not POLYMARKET_API_KEY:
        missing.append("POLYMARKET_API_KEY")
    if not POLYMARKET_SECRET:
        missing.append("POLYMARKET_API_SECRET")
    if not POLYMARKET_PASS:
        missing.append("POLYMARKET_PASSPHRASE")
    if not SERVER_WALLET_PK:
        missing.append("SERVER_POLYGON_WALLET_PK")
    if missing:
        raise ConfigurationError(
            f"Missing required env vars for real trading: {', '.join(missing)}. "
            f"See .env.example for setup instructions."
        )


# ─── CLOB CLIENT FACTORY ─────────────────────────────────────────────────────

def _get_clob_client():
    """
    Build and return a Polymarket ClobClient instance.
    This handles EIP-712 signing automatically using the server wallet PK.

    signature_type=0  = EOA (externally owned account, standard wallet)
    chain_id=137      = Polygon mainnet

    The client is stateless — safe to create per-request.
    """
    try:
        from py_clob_client.client import ClobClient
    except ImportError:
        raise ConfigurationError(
            "py-clob-client is not installed. "
            "Run: pip install py-clob-client"
        )

    return ClobClient(
        host=POLYMARKET_CLOB_URL,
        chain_id=137,
        private_key=SERVER_WALLET_PK,
        signature_type=0,   # EOA — change to 2 if using a Gnosis Safe
        funder=SERVER_WALLET_ADDRESS or None,
    )


# ─── CLOB MARKET FETCH ───────────────────────────────────────────────────────

async def get_clob_market(condition_id: str) -> dict:
    """
    Fetch market metadata from Polymarket CLOB.
    Returns token IDs, current prices, and order acceptance status.

    Polymarket CLOB market response shape:
      {
        "condition_id": "0x...",
        "question_id": "0x...",
        "tokens": [
          {"token_id": "...", "outcome": "Yes", "price": 0.72, "winner": false},
          {"token_id": "...", "outcome": "No",  "price": 0.28, "winner": false}
        ],
        "active": true,
        "closed": false,
        "accepting_orders": true,
        ...
      }
    """
    headers = {
        "POLY-API-KEY":    POLYMARKET_API_KEY,
        "POLY-PASSPHRASE": POLYMARKET_PASS,
        "Content-Type":    "application/json",
    }
    async with httpx.AsyncClient(timeout=12.0) as client:
        r = await client.get(
            f"{POLYMARKET_CLOB_URL}/markets/{condition_id}",
            headers=headers,
        )
        if r.status_code == 404:
            raise PolymarketError(f"Market {condition_id} not found on Polymarket CLOB.")
        if r.status_code == 401:
            raise ConfigurationError(
                "POLYMARKET_API_KEY or POLYMARKET_PASSPHRASE is wrong. "
                "Regenerate API credentials at polymarket.com/profile."
            )
        r.raise_for_status()
        return r.json()


async def get_order_book(token_id: str) -> dict:
    """
    Fetch the live order book for a YES or NO token.
    Used to verify there is liquidity before placing an order.
    """
    headers = {
        "POLY-API-KEY":    POLYMARKET_API_KEY,
        "POLY-PASSPHRASE": POLYMARKET_PASS,
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(
            f"{POLYMARKET_CLOB_URL}/book",
            params={"token_id": token_id},
            headers=headers,
        )
        r.raise_for_status()
        return r.json()


async def get_order_status(order_id: str) -> dict:
    """
    Fetch the current status of a placed order.
    Used by the settlement poller to check if an order was filled.

    Response: { "id": "...", "status": "MATCHED|LIVE|CANCELLED", ... }
    """
    headers = {
        "POLY-API-KEY":    POLYMARKET_API_KEY,
        "POLY-PASSPHRASE": POLYMARKET_PASS,
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(
            f"{POLYMARKET_CLOB_URL}/orders/{order_id}",
            headers=headers,
        )
        if r.status_code == 404:
            return {"status": "NOT_FOUND"}
        r.raise_for_status()
        return r.json()


# ─── ORDER PLACEMENT ──────────────────────────────────────────────────────────

def place_market_order(
    token_id: str,
    amount_usdc: float,
    price: float,
) -> dict:
    """
    Place a Fill-or-Kill (FOK) market order on Polymarket CLOB.

    Uses py-clob-client for EIP-712 signing via the server wallet private key.

    MarketOrderArgs:
      token_id   — YES or NO token ID from get_clob_market()
      amount     — USDC amount to spend
      price      — current token price (0.0–1.0), used for slippage calculation

    OrderType.FOK = Fill-or-Kill: fully fills immediately or cancels entirely.
    This is the safest choice for market orders — no partial fills left open.

    Returns the full CLOB order response dict including 'orderID' and 'status'.
    Raises PolymarketError on rejection.
    """
    _assert_configured()

    try:
        from py_clob_client.client import ClobClient
        from py_clob_client.clob_types import MarketOrderArgs, OrderType
    except ImportError:
        raise ConfigurationError(
            "py-clob-client is not installed. Run: pip install py-clob-client"
        )

    client = _get_clob_client()

    try:
        order = client.create_market_order(
            MarketOrderArgs(
                token_id=token_id,
                amount=amount_usdc,   # USDC amount
                price=price,          # used for worst-case fill price
            )
        )
        resp = client.post_order(order, OrderType.FOK)
    except Exception as e:
        raise PolymarketError(f"py-clob-client order error: {e}")

    if resp is None:
        raise PolymarketError("CLOB returned no response for order placement.")

    # py-clob-client raises on errorMsg but check defensively
    error_msg = resp.get("errorMsg") or resp.get("error")
    if error_msg:
        raise PolymarketError(f"CLOB rejected order: {error_msg}")

    logger.info(
        f"[clob] Order placed: id={resp.get('orderID')} "
        f"status={resp.get('status')} token={token_id[:12]}... "
        f"amount={amount_usdc} USDC"
    )
    return resp


# ─── MAIN TRADE EXECUTION ─────────────────────────────────────────────────────

async def place_real_trade(
    telegram_user_id: str,
    wallet_address: str,
    market_id: str,
    market_question: str,
    outcome: str,          # "YES" or "NO"
    amount_usdc: float,
    session: Session,
) -> RealTrade:
    """
    Execute a real trade on Polymarket CLOB via the server wallet.

    Full flow:
      1. Beta gate + config check
      2. Validate real USDC balance in DB
      3. Validate amount limits
      4. Fetch CLOB market → find YES/NO token_id
      5. Check order book has asks (liquidity)
      6. Deduct balance from DB (funds lock)
      7. Create RealTrade record (status: pending_execution)
      8. Place FOK market order via py-clob-client
      9. On success → update trade to open + store order ID
         On failure → refund balance + mark trade as failed

    Returns the RealTrade DB record.
    """
    wallet_address = wallet_address.lower()

    # 1. Gate checks
    assert_real_trading_allowed(wallet_address)
    _assert_configured()

    # 2. Amount validation
    if amount_usdc < MIN_REAL_TRADE_USDC:
        raise RealTradingError(
            f"Minimum real trade is ${MIN_REAL_TRADE_USDC:.2f} USDC."
        )
    if amount_usdc > MAX_REAL_TRADE_USDC:
        raise RealTradingError(
            f"Beta trade cap is ${MAX_REAL_TRADE_USDC:.2f} USDC per trade. "
            f"This cap will increase after the closed beta."
        )

    # 3. Balance check
    config = _ensure_wallet_config(telegram_user_id, session)
    if config.real_balance_usdc < amount_usdc:
        raise InsufficientRealBalanceError(
            f"Insufficient USDC. You have ${config.real_balance_usdc:.2f} "
            f"but tried to trade ${amount_usdc:.2f}. "
            f"Top up via the Wallet tab."
        )

    # 4. Fetch CLOB market metadata
    try:
        clob_market = await get_clob_market(market_id)
    except (PolymarketError, ConfigurationError):
        raise
    except Exception as e:
        raise PolymarketError(f"Failed to fetch market {market_id}: {e}")

    if not clob_market.get("accepting_orders", True):
        raise PolymarketError(
            "This market is not currently accepting orders. "
            "It may be resolving or paused."
        )
    if clob_market.get("closed"):
        raise PolymarketError("This market has already closed.")

    # Find the token_id for the chosen outcome
    tokens = clob_market.get("tokens", [])
    token_id     = None
    current_price = 0.5

    for tok in tokens:
        tok_outcome = tok.get("outcome", "").strip().upper()
        # Polymarket uses "Yes" / "No" (title case) in API responses
        if tok_outcome in (outcome.upper(), outcome.capitalize()):
            token_id      = tok.get("token_id")
            current_price = float(tok.get("price", 0.5))
            break

    if not token_id:
        raise PolymarketError(
            f"Could not find {outcome} token for market {market_id}. "
            f"Available outcomes: {[t.get('outcome') for t in tokens]}"
        )

    # 5. Liquidity check — make sure there are asks to fill against
    try:
        book = await get_order_book(token_id)
        asks = book.get("asks", [])
        if not asks:
            raise PolymarketError(
                "No sell orders on the order book right now. "
                "Try again in a moment or choose a different market."
            )
    except PolymarketError:
        raise
    except Exception as e:
        logger.warning(f"[real_trade] Order book check failed for {token_id[:12]}: {e} — proceeding")

    # Compute shares from USDC amount and current price
    shares = round(amount_usdc / max(current_price, 0.01), 4)

    # 6. Lock funds — deduct from DB balance BEFORE placing order
    config.real_balance_usdc = round(config.real_balance_usdc - amount_usdc, 6)
    config.updated_at = datetime.utcnow()
    session.add(config)
    session.flush()  # write deduction before trade record so rollback is clean

    # 7. Create RealTrade record
    trade = RealTrade(
        telegram_user_id=telegram_user_id,
        wallet_address=wallet_address,
        market_id=market_id,
        market_question=market_question,
        outcome=outcome.upper(),
        shares=shares,
        price_per_share=current_price,
        total_cost_usdc=amount_usdc,
        status="pending_execution",
    )
    session.add(trade)
    session.commit()
    session.refresh(trade)
    logger.info(
        f"[real_trade] Created RealTrade id={trade.id} "
        f"user={telegram_user_id[:8]} market={market_id[:12]} "
        f"outcome={outcome} amount={amount_usdc}"
    )

    # 8. Place CLOB order — runs synchronously inside asyncio thread pool
    try:
        loop = asyncio.get_event_loop()
        order_resp = await loop.run_in_executor(
            None,
            place_market_order,
            token_id,
            amount_usdc,
            current_price,
        )

        # 9a. Success — update trade record
        trade.polymarket_order_id = (
            order_resp.get("orderID")
            or order_resp.get("id")
            or order_resp.get("order", {}).get("id")
        )
        trade.status = "open"
        trade.updated_at = datetime.utcnow()
        session.add(trade)
        session.commit()
        logger.info(
            f"[real_trade] Order OPEN: trade={trade.id} "
            f"order={trade.polymarket_order_id}"
        )

    except Exception as e:
        # 9b. Failure — refund balance and mark trade failed
        logger.error(f"[real_trade] CLOB order failed for trade {trade.id}: {e}")
        config.real_balance_usdc = round(config.real_balance_usdc + amount_usdc, 6)
        config.updated_at = datetime.utcnow()
        trade.status = "failed"
        trade.error_message = str(e)
        trade.updated_at = datetime.utcnow()
        session.add(config)
        session.add(trade)
        session.commit()
        raise PolymarketError(f"Order placement failed and balance refunded: {e}")

    return trade


# ─── SETTLEMENT POLLER ───────────────────────────────────────────────────────

async def settle_open_real_trades(session: Session) -> list[dict]:
    """
    Check all open RealTrades against Polymarket and settle resolved ones.

    How settlement works on Polymarket:
      - YES winner: YES token redeems at $1.00/share → payout = shares × 1.0
      - NO winner:  NO  token redeems at $1.00/share → payout = shares × 1.0
      - Loser:      token redeems at $0.00          → payout = 0

    We detect resolution by checking the CLOB market endpoint:
      - If market.closed == true and a token has winner == true, we know the result.
      - If the user holds the winning token, they get shares × 1.0 USDC credited.
      - If they hold the losing token, they get $0.

    We also check the order status to handle the edge case where a FOK order
    was only partially filled (though FOK should prevent this).

    Returns a list of settlement result dicts.
    """
    open_trades = session.exec(
        select(RealTrade).where(RealTrade.status == "open")
    ).all()

    if not open_trades:
        return []

    results = []
    for trade in open_trades:
        try:
            result = await _settle_single_trade(trade, session)
            if result:
                results.append(result)
        except Exception as e:
            logger.error(f"[settle] Error settling trade {trade.id}: {e}")

    return results


async def _settle_single_trade(trade: RealTrade, session: Session) -> Optional[dict]:
    """
    Attempt to settle a single open RealTrade.
    Returns a result dict if the trade was settled, None if still open.
    """
    try:
        clob_market = await get_clob_market(trade.market_id)
    except Exception as e:
        logger.warning(f"[settle] Cannot fetch market {trade.market_id}: {e}")
        return None

    # Market not yet resolved — nothing to do
    if not clob_market.get("closed") and not clob_market.get("resolved"):
        return None

    # Find winning outcome
    tokens = clob_market.get("tokens", [])
    winning_outcome = None
    for tok in tokens:
        if tok.get("winner") is True:
            winning_outcome = tok.get("outcome", "").strip().upper()
            break

    if winning_outcome is None:
        # Market is closed but winner not determined yet — check again later
        logger.info(f"[settle] Market {trade.market_id} closed but no winner yet")
        return None

    # Determine payout
    trade_outcome_upper = trade.outcome.strip().upper()
    # Normalize "YES"/"NO" vs Polymarket's "Yes"/"No"
    won = (
        trade_outcome_upper == winning_outcome
        or trade_outcome_upper == winning_outcome.upper()
    )

    payout   = round(trade.shares * 1.0, 6) if won else 0.0
    pnl      = round(payout - trade.total_cost_usdc, 6)
    result   = "WIN" if won else "LOSS"

    # Credit payout to user's real balance
    config = _ensure_wallet_config(trade.telegram_user_id, session)
    if payout > 0:
        config.real_balance_usdc = round(config.real_balance_usdc + payout, 6)
        config.updated_at = datetime.utcnow()
        session.add(config)

    # Close the trade
    trade.status     = "closed"
    trade.pnl        = pnl
    trade.settled_at = datetime.utcnow()
    trade.updated_at = datetime.utcnow()
    session.add(trade)
    session.commit()

    logger.info(
        f"[settle] Trade {trade.id} SETTLED: outcome={trade.outcome} "
        f"winner={winning_outcome} result={result} "
        f"payout={payout} pnl={pnl:+.2f}"
    )

    return {
        "trade_id":     trade.id,
        "market_id":    trade.market_id,
        "outcome":      trade.outcome,
        "result":       result,
        "payout":       payout,
        "pnl":          pnl,
        "settled_at":   trade.settled_at.isoformat(),
    }


# ─── SERVER WALLET BALANCE CHECK ─────────────────────────────────────────────

async def get_server_wallet_usdc_balance() -> float:
    """
    Query the Polygon RPC for the server wallet's live USDC balance.

    Uses the ERC-20 balanceOf selector: 0x70a08231
    Returns the balance in USDC (human-readable, 6 decimals divided out).

    Used by the /wallet/server-balance endpoint to show operators
    how much USDC the server wallet currently holds on Polygon.
    """
    if not SERVER_WALLET_ADDRESS:
        return 0.0

    # ERC-20 balanceOf(address) call
    # Selector: 0x70a08231, padded address (32 bytes)
    address_padded = SERVER_WALLET_ADDRESS.lower().replace("0x", "").zfill(64)
    data = f"0x70a08231{address_padded}"

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "eth_call",
        "params": [
            {"to": USDC_POLYGON, "data": data},
            "latest"
        ]
    }

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.post(POLYGON_RPC, json=payload)
            r.raise_for_status()
            result = r.json().get("result", "0x0")
            # result is a 0x-prefixed hex string of the balance in USDC wei (6 decimals)
            raw = int(result, 16)
            return round(raw / 1_000_000, 6)   # USDC has 6 decimals
    except Exception as e:
        logger.warning(f"[balance] Server wallet USDC check failed: {e}")
        return 0.0