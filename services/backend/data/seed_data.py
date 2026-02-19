from sqlmodel import Session
from services.backend.data.database import engine
from services.backend.data.models import Market
from datetime import datetime, timedelta

def seed_markets():
    with Session(engine) as session:
        # Clear existing markets to prevent duplicates during testing
        session.query(Market).delete()
        
        # 1. THE MOMENTUM WINNER: Significant price jump
        m1 = Market(
            id="btc-100k-hourly",
            question="Will BTC hit $100k this hour?",
            category="Crypto",
            current_odds=0.85,  # High Momentum (0.50 -> 0.85)
            is_active=True,
            expires_at=datetime.utcnow() + timedelta(hours=1)
        )
        # Custom attributes for the engine to pick up
        m1.previous_odds = 0.50 
        m1.volume = 5000
        m1.avg_volume = 4000

        # 2. THE VOLUME SPIKE: Massive activity relative to average
        m2 = Market(
            id="eth-surge-hourly",
            question="Will ETH rise 2% this hour?",
            category="Crypto",
            current_odds=0.60,
            is_active=True,
            expires_at=datetime.utcnow() + timedelta(hours=1)
        )
        m2.previous_odds = 0.58
        m2.volume = 15000   # 10x Spike (15000 / 1500)
        m2.avg_volume = 1500

        # 3. THE "GHOST": Active but below MIN_LIQUIDITY (1000)
        m3 = Market(
            id="low-liq-market",
            question="Will a random altcoin pump?",
            category="Crypto",
            current_odds=0.90,
            is_active=True,
            expires_at=datetime.utcnow() + timedelta(hours=1)
        )
        m3.volume = 200 # Should be filtered out by signals_engine.py

        session.add(m1)
        session.add(m2)
        session.add(m3)
        session.commit()
        print("Database seeded with test markets!")

if __name__ == "__main__":
    seed_markets()