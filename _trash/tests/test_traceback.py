import asyncio
import traceback
from services.backend.api.advice import debug_openrouter

async def run():
    try:
        print("Running debug_openrouter...")
        res = await debug_openrouter()
        print("Success:", type(res))
    except Exception as e:
        print("EXCEPTION CAUGHT:")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run())
