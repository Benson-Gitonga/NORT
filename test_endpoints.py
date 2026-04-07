import httpx
import asyncio

async def test_x402(client):
    print("--- Testing /x402/verify (NULL wallet fix) ---")
    res = await client.post("http://localhost:8000/x402/verify", json={
        "proof": "demo",  # Dev bypass
        # No telegram_id or wallet passed, and no auth header, testing the fallback
    })
    print(f"Status: {res.status_code}")
    print(f"Response: {res.text}\n")

async def test_usage(client, wallet):
    print(f"--- Testing /agent/usage for {wallet} ---")
    res = await client.get(f"http://localhost:8000/agent/usage?wallet_address={wallet}")
    print(f"Status: {res.status_code}")
    print(f"Response: {res.text}\n")

async def test_advice(client, is_premium):
    tier = "PREMIUM" if is_premium else "FREE"
    print(f"--- Testing /agent/advice ({tier} TIER, Please wait 5-20s) ---")
    wallet = f"test_user_{tier.lower()}_123"
    try:
        res = await client.post("http://localhost:8000/agent/advice", json={
            "market_id": "0194c5aa-0797-76ae-bed7-1dcecfa9c445", # Using a common UUID format or hardcoded ID
            "telegram_id": wallet,
            "premium": is_premium
        }, timeout=60)
        print(f"Status: {res.status_code}")
        
        if res.status_code == 200:
            data = res.json()
            print(f"Summary: {data.get('summary', 'N/A')[:200]}...")
            print(f"Suggested Plan: {data.get('suggested_plan', 'N/A')}")
            print(f"Confidence: {data.get('confidence', 'N/A')}")
        else:
            print(res.text)
    except Exception as e:
        print(f"Error: {e}")
    print()

async def main():
    async with httpx.AsyncClient() as client:
        await test_x402(client)
        
        # Test Free Tier Advice
        await test_advice(client, is_premium=False)
        # Test Premium Tier Advice (Might hit 402 if using same user, or might use a demo override)
        # Assuming the backend lets `test_user_premium_123` pass or we rely on the prompt differences.
        # Note: If it fails with 402 Payment Required, it proves the gate is enforced. Let's see!
        await test_advice(client, is_premium=True)
        
        await test_usage(client, "test_user_free_123")

if __name__ == "__main__":
    asyncio.run(main())
