import requests
import json
import time

BASE_URL = "http://localhost:8000"

def test_debug():
    print("\n--- Testing Debug Endpoint ---")
    try:
        response = requests.get(f"{BASE_URL}/agent/advice/debug")
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            print("Successfully connected to OpenRouter!")
            # print(json.dumps(response.json(), indent=2))
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Failed to connect: {e}")

def test_advice(premium=False, language="en"):
    tier = "PREMIUM" if premium else "FREE"
    lang_tag = f" ({language.upper()})" if language != "en" else ""
    print(f"\n--- Testing {tier} Advice{lang_tag} ---")
    payload = {
        "market_id": "test-market-123",
        "premium": premium,
        "language": language
    }
    try:
        response = requests.post(f"{BASE_URL}/agent/advice", json=payload)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Summary: {data.get('summary')[:100]}...")
            print(f"Suggested Plan: {data.get('suggested_plan')}")
            print(f"Tools used: {data.get('tool_calls_used')}")
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Failed to connect: {e}")

if __name__ == "__main__":
    print("Ensure your backend is running (uvicorn services.backend.main:app --port 8000)")
    test_debug()
    # Test free and premium
    #test_advice(premium=False)
    #test_advice(premium=True)
    
    # Test Language Toggle (Swahili)
    test_advice(premium=True, language="sw")
