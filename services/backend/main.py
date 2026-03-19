from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session
import asyncio

from services.backend.api.signals import router as signals_router
from services.backend.api.markets import router as markets_router, sync_markets
from services.backend.api.trades import router as trades_router
from services.backend.api.wallet import router as wallet_router
from services.backend.api.advice import router as advice_router
from services.backend.api.leaderboard import router as leaderboard_router
from services.backend.api.fx import router as fx_router          # Phase 1: FX rates
from services.backend.api.mode import router as mode_router      # Phase 1: mode toggle
from services.backend.data.database import init_db, engine

# How often to auto-sync markets from Polymarket (in seconds)
SYNC_INTERVAL_SECONDS = 15 * 60  # 15 minutes


async def _market_sync_loop():
    """
    Background task that re-syncs markets from Polymarket every 15 minutes.
    Runs for the lifetime of the server — started in lifespan, cancelled on shutdown.
    Errors are caught and logged so a single failed sync never kills the loop.
    """
    while True:
        await asyncio.sleep(SYNC_INTERVAL_SECONDS)
        print(f"[scheduler] Auto-syncing markets from Polymarket...")
        try:
            with Session(engine) as session:
                sync_markets(session)
            print("[scheduler] Auto-sync complete.")
        except Exception as e:
            print(f"[scheduler] Auto-sync failed (will retry in {SYNC_INTERVAL_SECONDS // 60} min): {e}")


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

    # Start background sync loop
    sync_task = asyncio.create_task(_market_sync_loop())
    print(f"[scheduler] Market auto-sync started — every {SYNC_INTERVAL_SECONDS // 60} minutes.")

    yield

    # Clean shutdown — cancel the background task
    sync_task.cancel()
    try:
        await sync_task
    except asyncio.CancelledError:
        pass
    print("Shutting down...")


app = FastAPI(title="NORT Backend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── ROUTERS ─────────────────────────────────────────────────────────────────
# Each router is mounted twice: bare (legacy) + /api prefix (current standard).

app.include_router(markets_router)
app.include_router(markets_router,     prefix="/api")
app.include_router(signals_router)
app.include_router(signals_router,     prefix="/api")
app.include_router(trades_router)
app.include_router(trades_router,      prefix="/api")
app.include_router(wallet_router)
app.include_router(wallet_router,      prefix="/api")
app.include_router(advice_router)
app.include_router(advice_router,      prefix="/api")
app.include_router(leaderboard_router)
app.include_router(leaderboard_router, prefix="/api")
app.include_router(fx_router)          # GET /fx/rates
app.include_router(fx_router,          prefix="/api")   # GET /api/fx/rates
app.include_router(mode_router)        # GET|POST /wallet/mode
app.include_router(mode_router,        prefix="/api")   # GET|POST /api/wallet/mode


@app.api_route("/", methods=["GET", "HEAD"])
def root():
    return {"status": "online", "message": "NORT Backend is active."}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("services.backend.main:app", host="0.0.0.0", port=8000, reload=True)
