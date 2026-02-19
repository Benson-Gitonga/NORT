from fastapi import FastAPI
from contextlib import asynccontextmanager
from services.backend.api.signals import router as signals_router
from services.backend.api.markets import router as markets_router
from services.backend.data.database import init_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Initializing Database...")
    init_db()
    yield
    print("Shutting down...")

app = FastAPI(title="Polymarket AI Assistant", lifespan=lifespan)

app.include_router(markets_router)
app.include_router(signals_router)

@app.get("/")
def root():
    return {"status": "online", "message": "NORT Backend is active."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("services.backend.main:app", host="0.0.0.0", port=8000, reload=True)
