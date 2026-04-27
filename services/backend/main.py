import os
from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session

from services.backend.api.signals import router as signals_router
from services.backend.api.markets import router as markets_router, sync_markets
from services.backend.api.trades import router as trades_router
from services.backend.api.wallet import router as wallet_router
from services.backend.api.advice import router as advice_router
from services.backend.api.leaderboard import router as leaderboard_router
from services.backend.api.fx import router as fx_router
from services.backend.api.mode import router as mode_router
from services.backend.api.bridge import router as bridge_router
from services.backend.api.pretium import router as pretium_router
from services.backend.api.real_trades import router as real_trades_router
from services.backend.api.telegram import router as telegram_router
from services.backend.api.x402 import router as x402_router
from services.backend.data.database import init_db, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Initializing Database...")
    init_db()
    print("Syncing markets from Polymarket on startup...")
    try:
        with Session(engine) as session:
            sync_markets(session)
        print("Market sync complete.")
    except Exception as e:
        print(f"Market sync failed (will retry on first /markets request): {e}")
    yield
    print("Shutting down...")


from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="NORT Backend", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── CORS ──────────────────────────────────────────────────────────────────────
_CORE_ORIGINS = [
    "https://www.nortapp.online",
    "https://nortapp.online",
    "https://nort-landing-nine.vercel.app",
    "http://localhost:3000",
    "http://localhost:3001",
]
_extra = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]
ALLOWED_ORIGINS = list(dict.fromkeys(_CORE_ORIGINS + _extra))

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    # X-Wallet-Address is sent by authFetch so the backend can resolve the wallet
    # from the JWT without calling the Privy REST API on every request.
    allow_headers=["*", "Authorization", "Content-Type", "X-Wallet-Address"],
)

# ─── ROUTERS ─────────────────────────────────────────────────────────────────
for router in [
    markets_router, signals_router, trades_router, wallet_router,
    advice_router, telegram_router, x402_router, leaderboard_router,
    fx_router, mode_router, bridge_router, pretium_router, real_trades_router,
]:
    app.include_router(router)
    app.include_router(router, prefix="/api")


@app.api_route("/", methods=["GET", "HEAD"])
def root():
    return {"status": "online", "message": "NORT Backend is active."}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("services.backend.main:app", host="0.0.0.0", port=8000, reload=True)
