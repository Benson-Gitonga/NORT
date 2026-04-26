import sys
sys.path.insert(0, r'C:\Users\ELITEBOOK\OneDrive - Strathmore University\Desktop\NORT')
from services.backend.core.x402_verifier import has_any_confirmed_payment, resolve_user_identity
from services.backend.data.database import engine
from sqlmodel import Session

wallet = '0x690145312876Cf3423f2aCF3f5d8eEDcfD081948'

result = has_any_confirmed_payment(wallet)
print(f'has_any_confirmed_payment("{wallet}") = {result}')

with Session(engine) as session:
    user = resolve_user_identity(wallet, session)
    print(f'resolve_user_identity -> user.id={user.id if user else None} wallet={user.wallet_address if user else None}')
