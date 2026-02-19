from fastapi import FastAPI
from contextlib import asynccontextmanager

from services.backend.api.signals import router as signals_router
from services.backend.api.wallet import router as wallet_router
from services.backend.api.trades import router as trades_router
from services.backend.data.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # This runs when the server starts
    print("🚀 Initializing Database...")
    init_db()
    yield
    # This runs when the server stops
    print("Shutting down...")


app = FastAPI(title="Polymarket AI Assistant", lifespan=lifespan)

app.include_router(signals_router, prefix="/api")
app.include_router(wallet_router, prefix="/api")
app.include_router(trades_router, prefix="/api")


@app.get("/")
def root():
    return {"status": "online", "message": "NORT Backend is active."}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("services.backend.main:app", host="0.0.0.0", port=8000, reload=True)