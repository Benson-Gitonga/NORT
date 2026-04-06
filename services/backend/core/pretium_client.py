"""
Pretium API Client — HTTP adapter for on-ramp / off-ramp via Pretium Africa.

Pure HTTP layer. No database access. No business logic.
Auth: x-api-key header. Retries on transient failures.

Env vars:
  PRETIUM_API_KEY        — consumer key (used as x-api-key header)
  PRETIUM_SECRET_KEY     — secret key (used for webhook signature verification)
  PRETIUM_CHECKOUT_KEY   — checkout key (reserved for hosted checkout flows)
  PRETIUM_BASE_URL       — https://api.pretium.africa (or sandbox)
"""

import asyncio
import logging
import os
from typing import Any, Dict, Optional

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("pretium.client")


# ─── Exceptions ─────────────────────────────────────────────────────────────

class PretiumError(Exception):
    """Non-retryable Pretium API error."""
    def __init__(self, status_code: int, message: str, body: Any = None):
        self.status_code = status_code
        self.message = message
        self.body = body
        super().__init__(f"Pretium {status_code}: {message}")


class PretiumRetryableError(PretiumError):
    """Retryable Pretium API error (5xx / timeout)."""
    pass


# ─── Client ─────────────────────────────────────────────────────────────────

class PretiumClient:
    """
    Async HTTP client for Pretium Africa API.

    Auth: x-api-key header on every request.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        checkout_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.api_key = api_key or os.getenv("PRETIUM_API_KEY", "")
        self.secret_key = secret_key or os.getenv("PRETIUM_SECRET_KEY", "")
        self.checkout_key = checkout_key or os.getenv("PRETIUM_CHECKOUT_KEY", "")
        self.base_url = (base_url or os.getenv("PRETIUM_BASE_URL", "https://api.pretium.africa")).rstrip("/")
        self._http: Optional[httpx.AsyncClient] = None

    @property
    def http(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(timeout=30.0)
        return self._http

    async def close(self):
        if self._http and not self._http.is_closed:
            await self._http.aclose()

    # ── Core request with retries ────────────────────────────────────────────

    async def _request(
        self,
        method: str,
        path: str,
        json: Optional[Dict] = None,
        retries: int = 3,
    ) -> Any:
        """
        Make an authenticated request with exponential backoff on 5xx/429/timeout.
        4xx errors are NOT retried.
        """
        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
        }
        url = f"{self.base_url}{path}"
        last_error = None

        for attempt in range(retries):
            try:
                resp = await self.http.request(method, url, json=json, headers=headers)

                if resp.status_code >= 500:
                    wait = 3 ** attempt
                    logger.warning("pretium.api.5xx", extra={"status": resp.status_code, "attempt": attempt + 1, "path": path})
                    last_error = PretiumRetryableError(resp.status_code, resp.text)
                    if attempt < retries - 1:
                        await asyncio.sleep(wait)
                        continue
                    raise last_error

                if resp.status_code == 429:
                    wait = min(int(resp.headers.get("Retry-After", "5")), 60)
                    last_error = PretiumRetryableError(429, "Rate limited")
                    if attempt < retries - 1:
                        await asyncio.sleep(wait)
                        continue
                    raise last_error

                if resp.status_code >= 400:
                    body = None
                    try:
                        body = resp.json()
                    except Exception:
                        body = resp.text
                    logger.error("pretium.api.client_error", extra={"status": resp.status_code, "body": body, "path": path})
                    raise PretiumError(resp.status_code, str(body), body=body)

                return resp.json()

            except httpx.TimeoutException:
                logger.warning("pretium.api.timeout", extra={"attempt": attempt + 1, "path": path})
                last_error = PretiumRetryableError(408, "Request timed out")
                if attempt < retries - 1:
                    await asyncio.sleep(3 ** attempt)
                    continue
                raise last_error

            except (httpx.ConnectError, httpx.ReadError) as e:
                logger.warning("pretium.api.network_error", extra={"attempt": attempt + 1, "error": str(e), "path": path})
                last_error = PretiumRetryableError(0, f"Network error: {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(3 ** attempt)
                    continue
                raise last_error

        raise last_error or PretiumError(500, "Max retries exceeded")

    # ── Account ──────────────────────────────────────────────────────────────

    async def get_account_details(self) -> dict:
        """POST /account/detail — get merchant account info, wallets, networks."""
        return await self._request("POST", "/account/detail")

    async def get_wallet(self, country_id: int) -> dict:
        """POST /account/wallet/{country_id} — get fiat wallet balance for a country."""
        return await self._request("POST", f"/account/wallet/{country_id}")

    async def get_countries(self) -> dict:
        """POST /account/countries — list supported countries."""
        return await self._request("POST", "/account/countries")

    async def get_networks(self) -> dict:
        """POST /account/networks — list supported blockchain networks."""
        return await self._request("POST", "/account/networks")

    # ── Exchange Rate ────────────────────────────────────────────────────────

    async def get_exchange_rate(self, currency_code: str) -> dict:
        """POST /v1/exchange-rate — get buying/selling/quoted rates."""
        return await self._request("POST", "/v1/exchange-rate", json={
            "currency_code": currency_code,
        })

    # ── On-Ramp (Fiat → Crypto) ─────────────────────────────────────────────

    async def create_onramp(
        self,
        shortcode: str,
        amount: int,
        mobile_network: str,
        chain: str,
        asset: str,
        address: str,
        callback_url: str,
        fee: int = 0,
        currency_code: str = "KES",
    ) -> dict:
        """
        POST /v1/onramp/{currency} — collect mobile money, release stablecoins.

        Triggers STK push automatically for M-Pesa.
        """
        return await self._request("POST", f"/v1/onramp/{currency_code}", json={
            "shortcode": shortcode,
            "amount": amount,
            "mobile_network": mobile_network,
            "chain": chain,
            "asset": asset,
            "address": address,
            "callback_url": callback_url,
            "fee": fee,
        })

    # ── Off-Ramp (Crypto → Fiat) ────────────────────────────────────────────

    async def create_offramp(
        self,
        shortcode: str,
        amount: int,
        mobile_network: str,
        chain: str,
        transaction_hash: str,
        callback_url: str,
        fee: int = 0,
        currency_code: str = "KES",
        pay_type: str = "MOBILE",
    ) -> dict:
        """
        POST /v1/pay/{currency} — verify crypto payment, disburse fiat to mobile money.

        Requires transaction_hash proving crypto was sent to settlement wallet.
        """
        return await self._request("POST", f"/v1/pay/{currency_code}", json={
            "shortcode": shortcode,
            "amount": amount,
            "mobile_network": mobile_network,
            "chain": chain,
            "transaction_hash": transaction_hash,
            "callback_url": callback_url,
            "fee": fee,
            "type": pay_type,
        })

    # ── Status & History ─────────────────────────────────────────────────────

    async def get_transaction_status(
        self,
        transaction_code: str,
        currency_code: str = "KES",
    ) -> dict:
        """POST /v1/status/{currency} — get transaction status."""
        return await self._request("POST", f"/v1/status/{currency_code}", json={
            "transaction_code": transaction_code,
        })

    async def get_transactions(
        self,
        start_date: str,
        end_date: str,
        currency_code: str = "KES",
    ) -> dict:
        """POST /v1/transactions/{currency} — list transactions (max 3-day range)."""
        return await self._request("POST", f"/v1/transactions/{currency_code}", json={
            "start_date": start_date,
            "end_date": end_date,
        })

    # ── Refund ───────────────────────────────────────────────────────────────

    async def refund(self, chain: str, transaction_hash: str) -> dict:
        """POST /v1/refund — refund a transaction."""
        return await self._request("POST", "/v1/refund", json={
            "chain": chain,
            "transaction_hash": transaction_hash,
        })

    # ── Banks (for bank transfers) ───────────────────────────────────────────

    async def get_banks(self, currency_code: str = "KES") -> dict:
        """POST /v1/banks/{currency} — list supported banks."""
        return await self._request("POST", f"/v1/banks/{currency_code}")

    # ── Validation ────────────────────────────────────────────────────────────

    async def validate_phone(
        self,
        shortcode: str,
        mobile_network: str = "Safaricom",
        currency_code: str = "KES",
    ) -> dict:
        """POST /v1/validation/{currency} — validate phone number with MNO."""
        return await self._request("POST", f"/v1/validation/{currency_code}", json={
            "type": "MOBILE",
            "shortcode": shortcode,
            "mobile_network": mobile_network,
        })


# ─── Module-level singleton ─────────────────────────────────────────────────

_client: Optional[PretiumClient] = None


def get_pretium_client() -> PretiumClient:
    """Return a module-level singleton client."""
    global _client
    if _client is None:
        _client = PretiumClient()
    return _client
