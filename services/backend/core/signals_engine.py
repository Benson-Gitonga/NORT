# signals_engine.py
# Intern 2 — Signals Engine
# This file contains all the scoring logic.
# It is imported by api/signals.py to power the GET /signals endpoint.

from datetime import datetime
from typing import List, Dict

# ─────────────────────────────────────────────
# CONFIGURATION
# Tune these thresholds as you test
# ─────────────────────────────────────────────

MIN_LIQUIDITY = 1000.0      # Markets below this are too thin to trade
MOMENTUM_WEIGHT = 0.5       # How much price movement matters in final score
VOLUME_WEIGHT = 0.5         # How much volume spike matters in final score


# ─────────────────────────────────────────────
# STEP 1 — LIQUIDITY FILTER
# Gates every market before scoring.
# If a market fails this, it never gets ranked.
# ─────────────────────────────────────────────

def passes_liquidity_filter(market: Dict) -> bool:
    """
    Returns True if the market has enough liquidity to be worth ranking.
    Uses the 'volume' field as a proxy for liquidity.
    """
    volume = market.get("volume", 0)
    return volume >= MIN_LIQUIDITY


# ─────────────────────────────────────────────
# STEP 2 — MOMENTUM SCORE
# Measures how much the price has moved recently.
# Uses current_odds vs previous_odds stored in the market snapshot.
# Score is between 0.0 and 1.0
# ─────────────────────────────────────────────

def momentum_score(market: Dict) -> float:
    """
    Calculates a normalized momentum score based on price change.
    current_odds  = latest price (e.g. 0.72)
    previous_odds = price from last snapshot (e.g. 0.50)
    """
    current = market.get("current_odds", 0.5)
    previous = market.get("previous_odds", current)  # fallback: no change

    if previous == 0:
        return 0.0

    raw_change = abs(current - previous) / previous  # e.g. 0.44 = 44% move

    # Cap at 1.0 — a 100%+ move still scores 1.0
    return min(raw_change, 1.0)


# ─────────────────────────────────────────────
# STEP 3 — VOLUME SPIKE SCORE
# Measures how unusual the current volume is
# compared to a simple baseline.
# Score is between 0.0 and 1.0
# ─────────────────────────────────────────────

def volume_spike_score(market: Dict) -> float:
    """
    Compares current volume to a baseline average volume.
    A market with 3x its average volume scores higher.
    avg_volume is stored on the market dict — Intern 1 should provide this,
    or we fall back to a default baseline.
    """
    current_volume = market.get("volume", 0)
    avg_volume = market.get("avg_volume", 500)  # fallback baseline

    if avg_volume == 0:
        return 0.0

    ratio = current_volume / avg_volume  # e.g. 3.2 means 3.2x average

    # Normalize: cap at 5x = score of 1.0
    # So 1x = 0.2, 3x = 0.6, 5x+ = 1.0
    return min(ratio / 5.0, 1.0)


# ─────────────────────────────────────────────
# STEP 4 — COMPOSITE SCORE
# Combines momentum + volume into one final number.
# ─────────────────────────────────────────────

def composite_score(market: Dict) -> float:
    """
    Final ranking score for a market.
    Weighted combination of momentum and volume spike.
    Returns a value between 0.0 and 1.0
    """
    m = momentum_score(market)
    v = volume_spike_score(market)
    return round((MOMENTUM_WEIGHT * m) + (VOLUME_WEIGHT * v), 4)


# ─────────────────────────────────────────────
# STEP 5 — REASON STRING
# Every ranked market must explain WHY it ranked.
# This shows up in Telegram and on the Dashboard.
# ─────────────────────────────────────────────

def build_reason(market: Dict) -> str:
    """
    Generates a plain-English explanation for why this market ranked.
    Example output: "Price moved +18% with 3.2x average volume."
    """
    current = market.get("current_odds", 0.5)
    previous = market.get("previous_odds", current)
    volume = market.get("volume", 0)
    avg_volume = market.get("avg_volume", 500)

    # Price change as a percentage
    if previous > 0:
        price_change_pct = ((current - previous) / previous) * 100
        price_str = f"Price moved {price_change_pct:+.1f}%"
    else:
        price_str = "Price data unavailable"

    # Volume ratio
    if avg_volume > 0:
        ratio = volume / avg_volume
        volume_str = f"{ratio:.1f}x average volume"
    else:
        volume_str = "volume data unavailable"

    return f"{price_str} with {volume_str}."


# ─────────────────────────────────────────────
# STEP 6 — MAIN RANKING FUNCTION
# This is what signals.py calls.
# Takes a list of raw market dicts, returns ranked signals.
# ─────────────────────────────────────────────

def rank_markets(markets: List[Dict], top: int = 20) -> List[Dict]:
    """
    Main entry point for the signals engine.

    1. Filters out illiquid markets
    2. Scores each remaining market
    3. Sorts by composite score (highest first)
    4. Returns top N with reason strings attached

    Each returned dict includes:
      - market_id
      - question
      - score
      - reason
      - current_odds
      - volume
    """
    # Step 1: filter
    liquid_markets = [m for m in markets if passes_liquidity_filter(m)]

    # Step 2 & 3: score and sort
    scored = sorted(liquid_markets, key=composite_score, reverse=True)

    # Step 4: build output
    results = []
    for market in scored[:top]:
        score = composite_score(market)
        reason = build_reason(market)

        results.append({
            "market_id":    market.get("id"),
            "question":     market.get("question", "Unknown market"),
            "score":        score,
            "reason":       reason,
            "current_odds": market.get("current_odds"),
            "volume":       market.get("volume"),
            "category":     market.get("category", "general"),
            "expires_at":   str(market.get("expires_at", "")),
        })

    return results
