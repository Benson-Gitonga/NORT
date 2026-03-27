"""
market_watch.py — Task 7: Proactive Market Alert Scheduler

Called every 15 minutes by APScheduler (registered in main.py).
Fetches all active markets, scores them via rank_markets(), and pushes
a Telegram alert for any market scoring >= 0.75 that has not been
alerted in the last 2 hours.

AlertHistory table prevents duplicate alerts per user per market.
"""

import os
import httpx
from datetime import datetime, timezone, timedelta
from sqlmodel import Session, select

from services.backend.data.database import engine
from services.backend.data.models import Market, TelegramProfile, AlertHistory
from services.backend.core.signals_engine import rank_markets

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ALERT_SCORE_THRESHOLD = 0.75
ALERT_COOLDOWN_HOURS  = 2


def _already_alerted(session: Session, telegram_user_id: str, market_id: str) -> bool:
    """Returns True if this user was already alerted about this market in the last 2 hours."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=ALERT_COOLDOWN_HOURS)
    existing = session.exec(
        select(AlertHistory)
        .where(AlertHistory.telegram_user_id == telegram_user_id)
        .where(AlertHistory.market_id == market_id)
        .where(AlertHistory.sent_at >= cutoff)
    ).first()
    return existing is not None


def _record_alert(session: Session, telegram_user_id: str, market_id: str, score: float) -> None:
    """Writes an AlertHistory row so we don't re-alert within the cooldown window."""
    session.add(AlertHistory(
        telegram_user_id=telegram_user_id,
        market_id=market_id,
        score=score,
    ))
    session.commit()

def _send_telegram_alert(chat_id: str, text: str) -> None:
    """Sends a message to a Telegram user via the Bot API. Silently swallows errors."""
    if not TELEGRAM_BOT_TOKEN:
        print("[MarketWatch] TELEGRAM_BOT_TOKEN not set — skipping send.")
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        with httpx.Client(timeout=10) as client:
            resp = client.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"})
        if resp.status_code != 200:
            print(f"[MarketWatch] Telegram send failed ({resp.status_code}): {resp.text[:200]}")
    except Exception as e:
        print(f"[MarketWatch] Telegram send error (non-fatal): {e}")


def _format_alert(market: dict) -> str:
    score   = market.get("score", 0)
    q       = market.get("question", "Unknown market")
    mid     = market.get("market_id", "?")
    reason  = market.get("reason", "")
    odds    = int(float(market.get("current_odds", 0)) * 100)
    return (
        f"<b>📡 Market Alert</b>\n\n"
        f"<b>{q}</b>\n"
        f"Current odds: {odds}%  |  Score: {score:.2f}\n"
        f"{reason}\n\n"
        f"Type <code>/advice {mid}</code> for full AI analysis."
    )


async def run_market_watch() -> None:
    """
    Main scheduler entry point.
    1. Load all active markets from DB.
    2. Run rank_markets() to score them.
    3. For each market scoring >= 0.75, send an alert to every subscribed user
       who has not been alerted about that market in the last 2 hours.
    """
    print(f"[MarketWatch] Running at {datetime.now(timezone.utc).isoformat()}")

    with Session(engine) as session:
        # Fetch all active markets
        markets_raw = session.exec(select(Market).where(Market.is_active == True)).all()
        if not markets_raw:
            print("[MarketWatch] No active markets found.")
            return

        market_dicts = [
            {
                "id":            m.id,
                "question":      m.question,
                "category":      m.category,
                "current_odds":  m.current_odds,
                "previous_odds": m.previous_odds,
                "volume":        m.volume,
                "avg_volume":    m.avg_volume,
                "expires_at":    m.expires_at,
            }
            for m in markets_raw
        ]

        # Score and rank
        ranked = rank_markets(market_dicts, top=50)
        hot    = [m for m in ranked if m["score"] >= ALERT_SCORE_THRESHOLD]

        if not hot:
            print("[MarketWatch] No markets above alert threshold.")
            return

        print(f"[MarketWatch] {len(hot)} market(s) above threshold {ALERT_SCORE_THRESHOLD}.")

        # Get all subscribed users (those with a TelegramProfile)
        users = session.exec(select(TelegramProfile)).all()
        if not users:
            print("[MarketWatch] No Telegram users registered — nothing to alert.")
            return

        alerts_sent = 0
        for market in hot:
            for user in users:
                if _already_alerted(session, user.telegram_id, market["market_id"]):
                    continue
                msg = _format_alert(market)
                _send_telegram_alert(user.telegram_id, msg)
                _record_alert(session, user.telegram_id, market["market_id"], market["score"])
                alerts_sent += 1

        print(f"[MarketWatch] Done. {alerts_sent} alert(s) sent.")
