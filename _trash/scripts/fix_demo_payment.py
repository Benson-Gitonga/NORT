import sys
sys.path.insert(0, r'C:\Users\ELITEBOOK\OneDrive - Strathmore University\Desktop\NORT')
from services.backend.data.database import engine
from services.backend.data.models import Payment
from sqlmodel import Session, select

with Session(engine) as session:
    # Move the demo payment from the synthetic user (id=2) to the canonical wallet user (id=1)
    orphaned = session.exec(
        select(Payment).where(Payment.user_id == 2).where(Payment.market_id == '__global__')
    ).first()
    if orphaned:
        orphaned.user_id = 1
        session.commit()
        print(f'Migrated payment tx_hash={orphaned.tx_hash} to user_id=1')
    else:
        print('No orphaned payment found — nothing to migrate')

    # Verify
    payments = session.exec(select(Payment)).all()
    for p in payments:
        print(f'  user_id={p.user_id} market_id={p.market_id} confirmed={p.is_confirmed} tx={p.tx_hash[:30]}')
