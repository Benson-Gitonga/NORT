from sqlmodel import Session, select
from services.backend.data.database import engine
from services.backend.data.models import Payment

def reset_demo_tier():
    with Session(engine) as session:
        # Find all payments that were created using the "demo" bypass
        payments = session.exec(
            select(Payment).where(Payment.tx_hash.startswith("demo_"))
        ).all()
        
        count = 0
        for p in payments:
            session.delete(p)
            count += 1
            
        session.commit()
        print(f"Successfully deleted {count} demo payments. You are now back on the FREE tier!")

if __name__ == "__main__":
    reset_demo_tier()
