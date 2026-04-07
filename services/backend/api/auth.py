import os
import httpx
from fastapi import Header, HTTPException, Depends
from typing import Dict, Any, Optional

PRIVY_APP_ID = os.getenv("PRIVY_APP_ID")

async def get_current_user(authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    """
    Attempt to verify a Privy Bearer token.
    If the header is absent or verification fails, returns {"wallet": None}
    so endpoints can fall back to telegram_id / wallet from the request body.
    """
    if not authorization:
        return {"wallet": None}

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        return {"wallet": None}

    # Mock-auth bypass (development only)
    if os.getenv("NEXT_PUBLIC_USE_MOCK_AUTH", "false").lower() == "true":
        return {"wallet": "dev_user"}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                "https://auth.privy.io/api/v1/users/me",
                headers={
                    "Authorization": f"Bearer {token}",
                    "privy-app-id": PRIVY_APP_ID or "",
                },
            )

        if r.status_code != 200:
            # Token invalid — don't hard-block, let the endpoint use body fields
            return {"wallet": None}

        data = r.json()
        wallet = None
        if "wallet" in data and "address" in data["wallet"]:
            wallet = data["wallet"]["address"]
        elif "linked_accounts" in data:
            for account in data["linked_accounts"]:
                if account.get("type") == "wallet":
                    wallet = account.get("address")
                    break

        data["wallet"] = wallet  # may be None if no wallet linked
        return data

    except HTTPException:
        raise
    except Exception:
        # Network error talking to Privy — degrade gracefully
        return {"wallet": None}
