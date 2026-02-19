import os

from sqlmodel import SQLModel, Session, create_engine

# --- THE MISSING LINK: You MUST import your models here ---
from services.backend.data.models import User, Market, AISignal, Payment, Trade, PaperTrade, WalletConfig
# ----------------------------------------------------------

# This points to the /data folder in your monorepo
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
DB_PATH = os.path.join(BASE_DIR, "data", "assistant.db")
sqlite_url = f"sqlite:///{DB_PATH}"

# echo=True is great for you as the Lead; it shows the SQL commands in the terminal
engine = create_engine(sqlite_url, echo=True)


def init_db():
    print(f"Targeting database at: {os.path.abspath(DB_PATH)}")  # Helpful for debugging
    # This now knows about the tables because we imported them above
    SQLModel.metadata.create_all(engine)


def get_session():
    """FastAPI dependency that provides a database session."""
    with Session(engine) as session:
        yield session


if __name__ == "__main__":
    print("Building database tables...")
    init_db()
    print("Database built successfully!")