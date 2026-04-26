'use client';
/**
 * useTier.js
 * Tracks whether the current user is FREE or PREMIUM, and whether
 * they have hit the 15-message batch window limit.
 *
 * Limit behaviour (mirrors ChatGPT free tier):
 *   - 15 messages shared across /advice + /chat per 6-hour window.
 *   - Window is anchored to the FIRST message of each batch.
 *   - ALL 15 slots return at once at window_reset_at — no rolling refill.
 *   - No counter is shown in the UI; only the lock + reset time when hit.
 *   - Premium users (confirmed x402 payment) are exempt entirely.
 *
 * Falls back to localStorage for instant UI on reload (no loading flash).
 */
import { useState, useEffect, useCallback } from 'react';
import { BASE } from '@/lib/api';

// Optional: import getAccessToken if available in this context.
// We use a try/catch so this still works if Privy isn't loaded yet.
let _getAccessToken = null;
try {
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  _getAccessToken = require('@privy-io/react-auth').getAccessToken;
} catch { }

const FREE_DAILY_LIMIT = 10;

export function useTier() {
  const [tier, setTier]             = useState('free');
  const [atLimit, setAtLimit]       = useState(false);
  const [usedToday, setUsed]        = useState(0);
  const [windowResetAt, setResetAt] = useState(null);
  const [loading, setLoading]       = useState(true);

  const wallet =
    typeof window !== 'undefined'
      ? (window.localStorage?.getItem('walletAddress') || '').toLowerCase()
      : null;

  const refresh = useCallback(async () => {
    if (!wallet) { setLoading(false); return; }
    try {
      // Build auth headers — include Privy JWT so the backend resolves
      // identity from the token (same as every other authenticated endpoint).
      const headers = {};
      if (_getAccessToken) {
        try {
          const token = await _getAccessToken();
          if (token) headers['Authorization'] = `Bearer ${token}`;
        } catch { }
      }

      const res = await fetch(
        `${BASE}/agent/usage?wallet_address=${encodeURIComponent(wallet)}&t=${Date.now()}`,
        { headers }
      );
      if (res.ok) {
        const data = await res.json();
        const isPremium = data.is_premium ?? false;
        const used = data.used_recently ?? 0;
        setTier(isPremium ? 'premium' : 'free');
        setUsed(used);
        setAtLimit(!isPremium && (data.at_limit ?? false));
        setResetAt(data.window_reset_at ?? null);
        // cache for instant display on next load
        try {
          localStorage.setItem('nort_tier', isPremium ? 'premium' : 'free');
          localStorage.setItem('nort_at_limit', String(!isPremium && (data.at_limit ?? false)));
          localStorage.setItem('nort_reset_at', data.window_reset_at ?? '');
          localStorage.setItem('nort_used', String(used));
        } catch { }
      }
    } catch {
      // fallback to last-known localStorage values
      try {
        const cachedTier    = localStorage.getItem('nort_tier') || 'free';
        const cachedAtLimit = localStorage.getItem('nort_at_limit') === 'true';
        const cachedReset   = localStorage.getItem('nort_reset_at') || null;
        const cachedUsed    = parseInt(localStorage.getItem('nort_used') || '0', 10);
        setTier(cachedTier);
        setAtLimit(cachedAtLimit);
        setResetAt(cachedReset || null);
        setUsed(cachedUsed);
      } catch { }
    } finally {
      setLoading(false);
    }
  }, [wallet]);

  useEffect(() => { refresh(); }, [refresh]);

  useEffect(() => {
    if (typeof window === 'undefined') return undefined;
    const onRefresh = () => {
      // Clear stale cache so the next fetch always reflects the true backend state
      try {
        localStorage.removeItem('nort_tier');
        localStorage.removeItem('nort_at_limit');
        localStorage.removeItem('nort_reset_at');
        localStorage.removeItem('nort_used');
      } catch { }
      refresh();
    };
    window.addEventListener('nort-tier-refresh', onRefresh);
    return () => window.removeEventListener('nort-tier-refresh', onRefresh);
  }, [refresh]);

  /**
   * optimisticUpgrade — call immediately after a payment is confirmed.
   * Flips the tier badge to PREMIUM in React state + localStorage right away,
   * then fires a background refresh to sync with the backend.
   * This eliminates the visible lag between "Payment confirmed" and the badge
   * actually changing, which previously required a full /agent/usage round-trip.
   */
  const optimisticUpgrade = useCallback(() => {
    setTier('premium');
    setAtLimit(false);
    setResetAt(null);
    try {
      localStorage.setItem('nort_tier', 'premium');
      localStorage.setItem('nort_at_limit', 'false');
      localStorage.removeItem('nort_reset_at');
    } catch {}
    refresh(); // background sync — confirms with backend
  }, [refresh]);

  const remaining = tier === 'premium' ? null : Math.max(0, FREE_DAILY_LIMIT - usedToday);

  return { tier, atLimit, usedToday, remaining, windowResetAt, loading, refresh, optimisticUpgrade, FREE_DAILY_LIMIT };
}
