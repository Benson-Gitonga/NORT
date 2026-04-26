import sys
sys.path.insert(0, r'C:\Users\ELITEBOOK\OneDrive - Strathmore University\Desktop\NORT')
from services.backend.data.database import engine
from services.backend.data.models import Payment, User, AuditLog
from sqlmodel import Session, select
from datetime import datetime, timezone, timedelta

with Session(engine) as session:
    payments = session.exec(select(Payment)).all()
    print('=== PAYMENTS ===')
    for p in payments:
        print(f'  user_id={p.user_id} market_id={p.market_id} tx_hash={p.tx_hash} confirmed={p.is_confirmed}')

    window = datetime.now(timezone.utc) - timedelta(minutes=30)
    logs = session.exec(select(AuditLog).where(AuditLog.created_at >= window)).all()
    print('=== RECENT AUDIT LOGS (last 30 min) ===')
    for l in logs:
        print(f'  user={l.telegram_user_id} action={l.action} premium={l.premium} ts={l.created_at}')

    users = session.exec(select(User)).all()
    print('=== USERS ===')
    for u in users:
        print(f'  id={u.id} wallet={u.wallet_address} tg={u.telegram_id}')
