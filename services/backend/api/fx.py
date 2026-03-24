"""
FX Rate Cache Service + GET /fx/rates endpoint.

Maintains an in-memory cache of USD → local currency exchange rates,
refreshed every 60 seconds from the ExchangeRate-API (free tier).

All monetary values stored in the DB are in USDC (= USD).
This service lets the frontend display balances in KES, NGN, GHS etc.

Supported currencies: USD, KES, NGN, GHS, UGX, TZS, ZAR, EUR, GBP
"""

import asyncio
import httpx
import os
import logging
from datetime import datetime, timedelta
from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/fx", tags=["FX Rates"])

# ─── IN-MEMORY CACHE ─────────────────────────────────────────────────────────

_CACHE: dict = {}
_LAST_FETCH: datetime | None = None
_CACHE_TTL_SECONDS = 60

# Hardcoded fallback rates (used if the API is unreachable)
# Approximate as of March 2026 — kept conservative
_FALLBACK_RATES = {
    "USD": 1.0,
    "KES": 129.5,
    "NGN": 1580.0,
    "GHS": 15.2,
    "UGX": 3720.0,
    "TZS": 2580.0,
    "ZAR": 18.4,
    "EUR": 0.92,
    "GBP": 0.79,
}

_CURRENCY_SYMBOLS = {
    "USD": "$",
    "KES": "KSh",
    "NGN": "₦",
    "GHS": "GH₵",
    "UGX": "USh",
    "TZS": "TSh",
    "ZAR": "R",
    "EUR": "€",
    "GBP": "£",
}


# ─── FETCH FROM EXTERNAL API ─────────────────────────────────────────────────

async def _fetch_fresh_rates() -> dict:
    """
    Fetch live USD exchange rates from ExchangeRate-API (free tier, no key needed).
    Falls back to hardcoded rates if unreachable.
    """
    api_key = os.getenv("EXCHANGERATE_API_KEY", "")
    url = (
        f"https://v6.exchangerate-api.com/v6/{api_key}/latest/USD"
        if api_key
        else "https://open.er-api.com/v6/latest/USD"
    )

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()

        raw_rates = data.get("rates", {})
        rates = {}
        for currency in _FALLBACK_RATES:
            rates[currency] = float(raw_rates.get(currency, _FALLBACK_RATES[currency]))

        logger.info(f"[fx] Rates refreshed — KES={rates.get('KES')}, NGN={rates.get('NGN')}")
        return rates

    except Exception as e:
        logger.warning(f"[fx] Rate fetch failed ({e}) — using fallback rates")
        return _FALLBACK_RATES.copy()


# ─── CACHE ACCESSOR (called by other modules) ─────────────────────────────────

async def get_rates() -> dict:
    """
    Return cached rates, refreshing if the cache is older than TTL.
    This is the function other backend modules should import and call.
    """
    global _CACHE, _LAST_FETCH

    now = datetime.utcnow()
    if not _LAST_FETCH or (now - _LAST_FETCH) > timedelta(seconds=_CACHE_TTL_SECONDS):
        _CACHE = await _fetch_fresh_rates()
        _LAST_FETCH = now

    return _CACHE


def get_rates_sync() -> dict:
    """
    Synchronous accessor — returns the current cache without refreshing.
    Safe to call from non-async contexts (e.g. signal engine).
    Returns fallback rates if the cache is empty.
    """
    return _CACHE if _CACHE else _FALLBACK_RATES.copy()


def convert(usdc_amount: float, currency: str) -> dict:
    """
    Convert a USDC amount to a local currency.
    Returns { amount, currency, symbol, display }.

    Example:
        convert(12.50, "KES") → { amount: 1618.75, currency: "KES",
                                   symbol: "KSh", display: "KSh 1,618.75" }
    """
    rates = get_rates_sync()
    rate = rates.get(currency.upper(), 1.0)
    local_amount = round(usdc_amount * rate, 2)
    symbol = _CURRENCY_SYMBOLS.get(currency.upper(), currency.upper())
    return {
        "amount":   local_amount,
        "currency": currency.upper(),
        "symbol":   symbol,
        "display":  f"{symbol} {local_amount:,.2f}",
    }


# ─── ENDPOINT ─────────────────────────────────────────────────────────────────

@router.get("/rates")
async def fx_rates():
    """
    GET /fx/rates

    Returns current USD → local currency exchange rates.
    The dashboard polls this every 60 seconds to keep displayed balances fresh.

    Response:
    {
      "base": "USD",
      "rates": { "KES": 129.5, "NGN": 1580.0, ... },
      "symbols": { "KES": "KSh", "NGN": "₦", ... },
      "cached_at": "2026-03-18T12:00:00",
      "ttl_seconds": 60
    }
    """
    rates = await get_rates()
    return {
        "base":        "USD",
        "rates":       rates,
        "symbols":     _CURRENCY_SYMBOLS,
        "cached_at":   _LAST_FETCH.isoformat() if _LAST_FETCH else None,
        "ttl_seconds": _CACHE_TTL_SECONDS,
    }
