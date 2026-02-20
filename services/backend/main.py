from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware

from services.backend.api.signals import router as signals_router
from services.backend.api.wallet import router as wallet_router
from services.backend.api.trades import router as trades_router
from services.backend.api.markets import router as markets_router
from services.backend.api.advice import router as advice_router
from services.backend.data.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Initializing Database...")
    init_db()
    yield
    print("Shutting down...")


app = FastAPI(title="Polymarket AI Assistant", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(signals_router, prefix="/api")
app.include_router(wallet_router, prefix="/api")
app.include_router(trades_router, prefix="/api")
app.include_router(markets_router)
<<<<<<< HEAD
app.include_router(signals_router)
=======
app.include_router(signals_router)   # also mount without prefix so /signals/ works
>>>>>>> 25ad344e2b3076bca2e4bb0c8e9bf1e810422e4d
app.include_router(advice_router)


@app.get("/")
def root():
    return {"status": "online", "message": "NORT Backend is active."}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("services.backend.main:app", host="0.0.0.0", port=8000, reload=True)
