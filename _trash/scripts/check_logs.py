from sqlmodel import Session, select
from services.backend.data.database import engine
from services.backend.data.models import AuditLog

with Session(engine) as s:
    logs = s.exec(select(AuditLog)).all()
    print(f'Found {len(logs)} logs.')
    from collections import Counter
    c = Counter(l.telegram_user_id for l in logs)
    for user, count in c.items():
        print(f"User: {user}, Count: {count}")
