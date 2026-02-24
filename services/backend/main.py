from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session

from services.backend.api.signals import router as signals_router
from services.backend.api.markets import router as markets_router, sync_markets
from services.backend.api.trades import router as trades_router
from services.backend.api.wallet import router as wallet_router
from services.backend.api.advice import router as advice_router
from services.backend.api.leaderboard import router as leaderboard_router
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
        # Don't crash the server if Polymarket is unreachable at boot
        print(f"Market sync failed (will retry on first /markets request): {e}")

    yield
    print("Shutting down...")


app = FastAPI(title="NORT Backend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers once each — no duplicates
app.include_router(markets_router)
app.include_router(markets_router,    prefix="/api")
app.include_router(signals_router)
app.include_router(signals_router,    prefix="/api")
app.include_router(trades_router)
app.include_router(trades_router,     prefix="/api")
app.include_router(wallet_router)
app.include_router(wallet_router,     prefix="/api")
app.include_router(advice_router)
app.include_router(advice_router,     prefix="/api")
app.include_router(leaderboard_router)
app.include_router(leaderboard_router, prefix="/api")


@app.get("/")
def root():
    return {"status": "online", "message": "NORT Backend is active."}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("services.backend.main:app", host="0.0.0.0", port=8000, reload=True)
