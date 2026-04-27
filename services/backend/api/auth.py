import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional

import httpx
from fastapi import HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

PRIVY_APP_ID = os.getenv("PRIVY_APP_ID", "").strip()
logger = logging.getLogger(__name__)

bearer_scheme = HTTPBearer(auto_error=False)

# Cache valid tokens in memory to prevent rate-limiting against auth.privy.io
_token_cache: Dict[str, dict] = {}


def _extract_wallet_address(data: Dict[str, Any]) -> Optional[str]:
    wallet_obj = data.get("wallet")
    if isinstance(wallet_obj, dict) and wallet_obj.get("address"):
        return wallet_obj["address"]

    linked_accounts = data.get("linked_accounts") or []
    for account in linked_accounts:
        if account.get("type") == "wallet" and account.get("address"):
            return account["address"]
    return None


async def _verify_with_privy(token: str) -> Dict[str, Any]:
    if not PRIVY_APP_ID:
        logger.error("[Auth] PRIVY_APP_ID is not configured on the backend.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="PRIVY_APP_ID is not configured.",
        )

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0)) as client:
            response = await client.get(
                "https://auth.privy.io/api/v1/users/me",
                headers={
                    "Authorization": f"Bearer {token}",
                    "privy-app-id": PRIVY_APP_ID,
                    "Accept": "application/json",
                },
            )
    except httpx.RequestError as exc:
        logger.error(f"[Auth] Could not reach Privy /users/me: {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth provider unavailable.",
        )

    if response.status_code != 200:
        preview = (response.text or "")[:200]
        logger.warning(f"[Auth] Privy rejected token: {response.status_code} {preview}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
        )

    return response.json()


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
) -> Dict[str, Any]:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header.",
        )
    if credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization scheme must be Bearer.",
        )

    token = (credentials.credentials or "").strip()
    if not token or token in {"null", "undefined"}:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token.",
        )

    # If using mock auth and enabled in env, bypass verified
    if os.getenv("NEXT_PUBLIC_USE_MOCK_AUTH", "false").lower() == "true":
        return {"wallet": "dev_user"}

    now = datetime.utcnow().timestamp()
    cached = _token_cache.get(token)
    if cached and now < cached["expires_at"]:
        return cached["data"]

    data = await _verify_with_privy(token)
    wallet = _extract_wallet_address(data)
    if not wallet:
        header_wallet = (request.headers.get("x-wallet-address") or "").strip().lower()
        if header_wallet and header_wallet not in {"null", "undefined"}:
            wallet = header_wallet
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Privy user has no wallet address.",
            )

    data["wallet"] = wallet.lower()
    _token_cache[token] = {
        "data": data,
        "expires_at": now + 900,  # 15 minutes
    }
    return data
