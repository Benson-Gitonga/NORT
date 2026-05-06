'use client';
import { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { useAuth } from '@/hooks/useAuth';
import { BASE, authFetch } from '@/lib/api';

const TradingModeContext = createContext({
  mode: 'paper',
  gates: {},
  canSwitchToReal: false,
  loading: true,
  refresh: () => {},
  setMode: async () => {},
});

export function TradingModeProvider({ children }) {
  const { walletAddress, isAuthed } = useAuth();
  const [mode, setModeState] = useState('paper');
  const [gates, setGates] = useState({});
  const [canSwitchToReal, setCanSwitchToReal] = useState(false);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    if (!walletAddress) return;
    try {
      const res = await authFetch(
        `${BASE}/api/wallet/mode?wallet_address=${encodeURIComponent(walletAddress)}`
      );
      if (!res.ok) return;
      const data = await res.json();
      setModeState(data.trading_mode || 'paper');
      setGates(data.gates || {});
      setCanSwitchToReal(data.can_switch_to_real || false);
    } catch (e) {
      console.warn('[TradingMode] fetch failed:', e);
    } finally {
      setLoading(false);
    }
  }, [walletAddress]);

  useEffect(() => {
    if (isAuthed && walletAddress) refresh();
    else setLoading(false);
  }, [isAuthed, walletAddress, refresh]);

  // Switch mode — calls backend, enforces all gates server-side
  const setMode = useCallback(async (newMode, confirmed = false) => {
    if (!walletAddress) throw new Error('No wallet connected');
    const res = await authFetch(`${BASE}/api/wallet/mode`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        wallet_address: walletAddress,
        mode: newMode,
        confirmed,
      }),
    });
    const data = await res.json();
    if (!res.ok) throw data; // throw the full error object with gates info
    await refresh();
    return data;
  }, [walletAddress, refresh]);

  return (
    <TradingModeContext.Provider value={{ mode, gates, canSwitchToReal, loading, refresh, setMode }}>
      {children}
    </TradingModeContext.Provider>
  );
}

export function useTradingMode() {
  return useContext(TradingModeContext);
}
