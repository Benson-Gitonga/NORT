import os
import httpx
from fastapi import Header, HTTPException, Depends
from typing import Dict, Any

PRIVY_APP_ID = os.getenv("PRIVY_APP_ID")

async def get_current_user(authorization: str = Header(...)) -> Dict[str, Any]:
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(401, "Missing token")
    
    # If using mock auth and enabled in env, bypass verified
    if os.getenv("NEXT_PUBLIC_USE_MOCK_AUTH", "false").lower() == "true":
        return {"wallet": "dev_user"}
        
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                "https://auth.privy.io/api/v1/users/me",
                headers={
                    "Authorization": f"Bearer {token}",
                    "privy-app-id": PRIVY_APP_ID,
                }
            )
        if r.status_code != 200:
            raise HTTPException(401, "Invalid token")
        
        data = r.json()
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
        return data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(401, f"Token verification failed: {e}")
