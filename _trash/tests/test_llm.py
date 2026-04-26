import httpx
import asyncio
import json

async def test_llm():
    print("Testing free tier advice to check raw summary formatting...")
    async with httpx.AsyncClient(timeout=60) as client:
        res = await client.post("http://localhost:8000/agent/advice", json={
            "market_id": "1808032",
            "telegram_id": "0x690145312876Cf3423f2aCF3f5d8eEDcfD081948",
            "premium": False,
            "user_message": "/advice 1808032"
        })
        print(f"Status: {res.status_code}")
        body = res.json()
        print(json.dumps(body, indent=2))

if __name__ == "__main__":
    asyncio.run(test_llm())
