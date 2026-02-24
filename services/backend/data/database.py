import os
from sqlmodel import SQLModel, Session, create_engine

# Import all models so SQLModel knows about every table
from services.backend.data.models import (
    User, Market, AISignal, Payment, Trade,
    PaperTrade, WalletConfig, LeaderboardSnapshot
)

# ─────────────────────────────────────────────
# DATABASE URL
# Locally:   uses SQLite (no setup needed)
# On Render: uses Neon PostgreSQL (set DATABASE_URL in Render env vars)
# ─────────────────────────────────────────────

DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    # Neon / PostgreSQL — used on Render
    # Neon connection strings sometimes use "postgres://" (old format)
    # SQLAlchemy requires "postgresql://" so we fix it here
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

    engine = create_engine(
        DATABASE_URL,
        echo=False,  # Set True temporarily if you need to debug queries
    )
    print("Database: Neon PostgreSQL")

else:
    # Local development — SQLite fallback
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    DB_PATH  = os.path.join(BASE_DIR, "data", "assistant.db")
    sqlite_url = f"sqlite:///{DB_PATH}"

    engine = create_engine(
        sqlite_url,
        connect_args={"check_same_thread": False},
        echo=True,
    )
    print(f"Database: SQLite at {os.path.abspath(DB_PATH)}")


def init_db():
    """Create all tables if they don't exist. Safe to call on every startup."""
    SQLModel.metadata.create_all(engine)
    print("Database tables ready.")


def get_session():
    """FastAPI dependency that provides a database session."""
    with Session(engine) as session:
        yield session


if __name__ == "__main__":
    print("Building database tables...")
    init_db()
    print("Done.")
