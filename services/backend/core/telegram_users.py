from datetime import datetime
from typing import Optional

from sqlmodel import Session, select

from services.backend.core.paper_trading import connect_wallet, get_user_by_telegram
from services.backend.data.models import TelegramProfile


def upsert_telegram_profile(
    session: Session,
    telegram_id: str,
    username: Optional[str] = None,
    preferred_language: Optional[str] = None,
) -> TelegramProfile:
    telegram_id = str(telegram_id).strip()
    if not telegram_id:
        raise ValueError("telegram_id is required")

    profile = session.exec(
        select(TelegramProfile).where(TelegramProfile.telegram_id == telegram_id)
    ).first()

    if not profile:
        profile = TelegramProfile(telegram_id=telegram_id)

    user = get_user_by_telegram(telegram_id, session)
    if not user:
        synthetic_wallet = f"telegram:{telegram_id}"
        user = connect_wallet(
            wallet_address=synthetic_wallet,
            session=session,
            telegram_id=telegram_id,
            username=username or f"telegram_{telegram_id}",
        )

    profile.user_id = user.id
    if username is not None and username.strip():
        profile.username = username.strip()
    if preferred_language is not None and preferred_language.strip():
        profile.preferred_language = normalize_language(preferred_language)
    profile.updated_at = datetime.utcnow()

    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


def get_telegram_profile(session: Session, telegram_id: str) -> Optional[TelegramProfile]:
    return session.exec(
        select(TelegramProfile).where(TelegramProfile.telegram_id == str(telegram_id))
    ).first()


def set_language(session: Session, telegram_id: str, language: str) -> TelegramProfile:
    profile = upsert_telegram_profile(session, telegram_id)
    profile.preferred_language = normalize_language(language)
    profile.updated_at = datetime.utcnow()
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


def set_pending_premium_market(
    session: Session,
    telegram_id: str,
    market_id: Optional[str],
) -> TelegramProfile:
    profile = upsert_telegram_profile(session, telegram_id)
    profile.pending_premium_market_id = market_id
    profile.updated_at = datetime.utcnow()
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


def update_permissions(
    session: Session,
    telegram_id: str,
    auto_trade: Optional[bool],
    limit: Optional[float],
) -> TelegramProfile:
    profile = upsert_telegram_profile(session, telegram_id)
    if auto_trade is not None:
        profile.auto_trade_enabled = auto_trade
    if limit is not None:
        if limit <= 0:
            raise ValueError("limit must be greater than 0")
        profile.auto_trade_limit = limit
    profile.updated_at = datetime.utcnow()
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


def normalize_language(language: str) -> str:
    normalized = (language or "en").strip().lower()
    if normalized not in {"en", "sw"}:
        raise ValueError("language must be 'en' or 'sw'")
    return normalized
