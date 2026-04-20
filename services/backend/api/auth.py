"""
auth.py — Privy JWT verification for NORT backend.

Privy issues signed JWT access tokens. We verify them locally using the
Privy public JWK set (cached in memory) rather than making a network call
on every request. This is ~10x faster and does not require a Privy API call.

Flow:
  1. Frontend calls getAccessToken() from @privy-io/react-auth
  2. Sends as "Authorization: Bearer <jwt>" header
  3. We verify the JWT signature against Privy's JWKS endpoint
  4. Extract wallet address from linked_accounts claim

Falls back to {"wallet": None} on any failure so all endpoints degrade
gracefully and can use telegram_id / wallet_address from the request body.
"""

import os
import httpx
import time
from fastapi import Header
from typing import Dict, Any, Optional

PRIVY_APP_ID = os.getenv("PRIVY_APP_ID", "").strip()

# ── JWKS cache ──────────────────────────────────────────────────────────────
# Privy's public keys rotate rarely. Cache for 24h to avoid hammering JWKS.
_jwks_cache: dict = {"keys": None, "fetched_at": 0}
_JWKS_TTL = 86400  # 24 hours

async def _get_privy_jwks() -> list:
    now = time.time()
    if _jwks_cache["keys"] and (now - _jwks_cache["fetched_at"]) < _JWKS_TTL:
        return _jwks_cache["keys"]
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                f"https://auth.privy.io/api/v1/apps/{PRIVY_APP_ID}/jwks.json",
                headers={"privy-app-id": PRIVY_APP_ID},
            )
            if r.status_code == 200:
                keys = r.json().get("keys", [])
                _jwks_cache["keys"] = keys
                _jwks_cache["fetched_at"] = now
                return keys
    except Exception as e:
        print(f"[Auth] JWKS fetch failed: {e}")
    return _jwks_cache.get("keys") or []

async def get_current_user(
    authorization: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    """
    Verify a Privy Bearer JWT and return the user dict with a 'wallet' key.
    Returns {"wallet": None} on any failure — endpoints use body fields as fallback.
    """
    if not authorization:
        return {"wallet": None}

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        return {"wallet": None}

    # Dev mock bypass — only active when NEXT_PUBLIC_USE_MOCK_AUTH=true
    if os.getenv("NEXT_PUBLIC_USE_MOCK_AUTH", "false").lower() == "true":
        return {"wallet": "dev_user"}

    # ── Try local JWT verification first (fast, no network) ─────────────────
    try:
        import jwt as pyjwt
        jwks = await _get_privy_jwks()
        if jwks:
            from jwt import PyJWKClient, PyJWKSet
            jwk_set = PyJWKSet.from_dict({"keys": jwks})
            # Find signing key — try each key until one works
            for jwk in jwks:
                try:
                    key_obj = pyjwt.algorithms.RSAAlgorithm.from_jwk(jwk)
                    payload = pyjwt.decode(
                        token,
                        key_obj,
                        algorithms=["RS256"],
                        audience=PRIVY_APP_ID,
                        options={"verify_exp": True},
                    )
                    wallet = _extract_wallet_from_payload(payload)
                    payload["wallet"] = wallet
                    return payload
                except Exception:
                    continue
    except ImportError:
        pass  # PyJWT not installed — fall through to network verification
    except Exception as e:
        print(f"[Auth] JWT verify error: {e}")

    # ── Fallback: verify via Privy network call (slower but always works) ────
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                "https://auth.privy.io/api/v1/users/me",
                headers={
                    "Authorization": f"Bearer {token}",
                    "privy-app-id": PRIVY_APP_ID,
                },
            )
        if r.status_code != 200:
            return {"wallet": None}
        data = r.json()
        data["wallet"] = _extract_wallet_from_payload(data)
        return data
    except Exception:
        return {"wallet": None}


def _extract_wallet_from_payload(data: dict) -> Optional[str]:
    """Pull the wallet address out of either a JWT payload or Privy user dict."""
    # Embedded wallet field (some Privy JWT shapes)
    if "wallet" in data and isinstance(data["wallet"], dict):
        addr = data["wallet"].get("address")
        if addr:
            return addr.lower()

    # linked_accounts array (Privy user object shape)
    for account in data.get("linked_accounts", []):
        if account.get("type") in ("wallet", "smart_wallet"):
            addr = account.get("address")
            if addr:
                return addr.lower()

    # sub claim is the Privy user ID — not a wallet, but better than None
    # Return None — callers will fall back to request body telegram_id
    return None
