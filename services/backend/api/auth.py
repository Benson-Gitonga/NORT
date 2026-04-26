import os
import httpx
import logging
from fastapi import Header, HTTPException, Depends
from typing import Dict, Any
from datetime import datetime

PRIVY_APP_ID = os.getenv("PRIVY_APP_ID")
logger = logging.getLogger(__name__)

# Cache valid tokens in memory to prevent rate-limiting against auth.privy.io
_token_cache: Dict[str, dict] = {}

async def _verify_with_privy(token: str) -> Dict[str, Any]:
    async with httpx.AsyncClient() as client:
        r = await client.get(
            "https://auth.privy.io/api/v1/users/me",
            headers={
                "Authorization": f"Bearer {token}",
                "privy-app-id": PRIVY_APP_ID,
            }
        )
    if r.status_code != 200:
        logger.error(f"[Auth] Privy rejected token: {r.status_code} {r.text}")
        raise HTTPException(r.status_code if r.status_code != 429 else 401, f"Invalid token: {r.status_code}")
    return r.json()

async def get_current_user(authorization: str = Header(...)) -> Dict[str, Any]:
    token = authorization.removeprefix("Bearer ").strip()
    if not token or token == "null" or token == "undefined":
        raise HTTPException(401, "Missing token")
    
    # If using mock auth and enabled in env, bypass verified
    if os.getenv("NEXT_PUBLIC_USE_MOCK_AUTH", "false").lower() == "true":
        return {"wallet": "dev_user"}
        
    now = datetime.utcnow().timestamp()
    
    # Return cached data if valid for 1 hour 
    # (Since Privy issues short-lived JWTs anyway, this acts like a fast-path cache)
    if token in _token_cache:
        cached = _token_cache[token]
        if now < cached["expires_at"]:
            return cached["data"]

    try:
        data = await _verify_with_privy(token)
        
        wallet = None
        if "wallet" in data and "address" in data["wallet"]:
            wallet = data["wallet"]["address"]
        elif "linked_accounts" in data:
            for account in data["linked_accounts"]:
                if account.get("type") == "wallet":
                    wallet = account.get("address")
                    break
                    
        if not wallet:
            raise HTTPException(401, "User has no wallet address")
            
        data["wallet"] = wallet
        
        # Save to cache (cache for 15 minutes)
        _token_cache[token] = {
            "data": data,
            "expires_at": now + 900
        }
        
        return data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Auth] Exception during token verification: {e}")
        raise HTTPException(401, f"Token verification failed: {str(e)}")
