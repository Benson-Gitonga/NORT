import os
import logging
import jwt
from fastapi import Header, HTTPException
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

PRIVY_APP_ID = os.getenv("PRIVY_APP_ID", "cmlt2ysh2000j0blgjeoz612l")

# PyJWKClient fetches and caches Privy's public keys.
# Verifies JWT signature locally — no round-trip to Privy API, no rate limits.
jwks_url = f"https://auth.privy.io/api/v1/apps/{PRIVY_APP_ID}/jwks.json"
jwks_client = jwt.PyJWKClient(jwks_url, cache_keys=True)


def _decode_privy_token(token: str) -> Dict[str, Any]:
    """
    Cryptographically verify a Privy access token using JWKS.
    Returns the JWT payload on success.
    Raises HTTPException(401) on any failure.
    """
    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256"],
            audience=PRIVY_APP_ID,
            issuer="privy.io",
            options={"verify_exp": True},
        )
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("[auth] Privy token expired")
        raise HTTPException(401, "Token expired. Please reconnect your wallet.")
    except jwt.InvalidAudienceError:
        logger.error(f"[auth] Token audience mismatch — expected {PRIVY_APP_ID}")
        raise HTTPException(401, "Token audience mismatch. Check PRIVY_APP_ID env var.")
    except jwt.PyJWKClientError as e:
        logger.error(f"[auth] JWKS fetch failed: {e}")
        raise HTTPException(401, f"Could not fetch Privy signing keys: {e}")
    except jwt.DecodeError as e:
        logger.warning(f"[auth] Token decode error: {e}")
        raise HTTPException(401, "Malformed token.")
    except Exception as e:
        logger.error(f"[auth] Unexpected token verification error: {e}")
        raise HTTPException(401, f"Token verification failed: {e}")


async def get_current_user(
    authorization: str = Header(..., description="Bearer <privy-access-token>"),
    x_wallet_address: Optional[str] = Header(None, alias="X-Wallet-Address"),
) -> Dict[str, Any]:
    """
    FastAPI dependency that verifies the Privy JWT and returns user identity.

    WHY we need X-Wallet-Address:
        Privy's ACCESS tokens (short-lived JWTs) do NOT embed linked_accounts
        or wallet addresses in their payload. That data is only in the user
        object from the Privy REST API. Rather than making an API call per
        request (slow, rate-limited), we take the wallet address from the
        frontend (which already has it from usePrivy()) and verify only that
        the JWT is valid and belongs to the same Privy user.

    Security:
        The JWT is verified cryptographically via JWKS — it cannot be forged.
        The wallet address from X-Wallet-Address is cross-checked: if the JWT
        payload contains a wallet (some Privy token versions include it), we
        verify they match. If it doesn't, we trust the frontend-supplied value
        since the JWT already proves the user is authenticated with Privy.

    Returns:
        { "privy_user_id": str, "wallet": str }
    """
    # ── Extract token ────────────────────────────────────────────────────────
    if not authorization:
        raise HTTPException(401, "Authorization header required.")

    token = authorization.removeprefix("Bearer ").strip()
    if not token or token in ("null", "undefined", ""):
        raise HTTPException(401, "Missing or empty Bearer token.")

    # ── Mock auth bypass (dev only, never in production) ─────────────────────
    if os.getenv("NEXT_PUBLIC_USE_MOCK_AUTH", "false").lower() == "true":
        wallet = (x_wallet_address or "dev_user").lower()
        return {"privy_user_id": "mock_user", "wallet": wallet}

    # ── Verify JWT signature offline via JWKS ─────────────────────────────────
    payload = _decode_privy_token(token)

    privy_user_id = payload.get("sub") or payload.get("userId") or ""

    # ── Extract wallet from JWT payload (if present) ──────────────────────────
    # Privy embeds wallet in different places depending on SDK version:
    jwt_wallet: Optional[str] = None

    # Pattern 1: { "wallet": { "address": "0x..." } }
    if isinstance(payload.get("wallet"), dict):
        jwt_wallet = payload["wallet"].get("address")

    # Pattern 2: { "linked_accounts": [{ "type": "wallet", "address": "0x..." }] }
    if not jwt_wallet and isinstance(payload.get("linked_accounts"), list):
        for acct in payload["linked_accounts"]:
            if acct.get("type") == "wallet":
                jwt_wallet = acct.get("address")
                break

    # Pattern 3: { "address": "0x..." } at top level
    if not jwt_wallet and payload.get("address"):
        jwt_wallet = payload["address"]

    # ── Resolve final wallet address ──────────────────────────────────────────
    frontend_wallet = (x_wallet_address or "").strip().lower() or None

    if jwt_wallet:
        # JWT has a wallet — use it as the authoritative value
        wallet = jwt_wallet.lower()
        # If frontend also sent one, warn if they don't match (don't hard-fail,
        # Privy can have multiple linked wallets)
        if frontend_wallet and frontend_wallet != wallet:
            logger.warning(
                f"[auth] X-Wallet-Address ({frontend_wallet[:10]}) "
                f"differs from JWT wallet ({wallet[:10]}) — using JWT wallet"
            )
    elif frontend_wallet:
        # JWT doesn't carry wallet (common for Privy access tokens) —
        # trust the frontend value since the JWT signature already proved identity
        wallet = frontend_wallet
    else:
        # No wallet anywhere — still allow through for endpoints that don't need it
        # (e.g. /signals, /markets which are soft-gated)
        wallet = privy_user_id.lower() or "unknown"
        logger.warning(
            f"[auth] No wallet address found for privy_user_id={privy_user_id[:16]} "
            f"— endpoints requiring wallet will use privy_user_id as fallback"
        )

    return {
        "privy_user_id": privy_user_id,
        "wallet":        wallet,
    }
