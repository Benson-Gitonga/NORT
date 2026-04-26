'use client';
import React, { useState, useEffect, useRef } from 'react';
import { getTrades, getWallet, getPositionValue, sellTrade, getAchievements } from '@/lib/api';
import { useAchievement } from '@/components/AchievementContext';
import { useTelegram } from '@/hooks/useTelegram';
import { useAuth } from '@/hooks/useAuth';
import AuthGate from '@/components/AuthGate';
import Navbar from '@/components/Navbar';

// ── Sell confirmation modal ───────────────────────────────────────────────────
function SellModal({ trade, onConfirm, onClose }) {
  const [value, setValue]     = useState(null);
  const [loading, setLoading] = useState(true);
  const [selling, setSelling] = useState(false);
  const [error, setError]     = useState(null);

  useEffect(() => {
    getPositionValue(trade.id)
      .then(v => setValue(v))
      .catch(() => {
        // Fallback: calculate from what we already have
        setValue({
          entry_price:   trade.price,
          current_price: trade.currentPrice ?? trade.price,
          entry_value:   trade.amount,
          current_value: trade.currentValue ?? trade.amount,
          unrealized_pnl: trade.unrealizedPnl ?? 0,
          pnl_pct:       0,
          shares:        trade.shares,
        });
      })
      .finally(() => setLoading(false));
  }, [trade.id]);

  const handleSell = async () => {
    setSelling(true);
    setError(null);
    try {
      await onConfirm(trade.id);
      onClose();
    } catch (e) {
      setError(e.message || 'Sell failed. Try again.');
      setSelling(false);
    }
  };

  const fmt    = (n) => n >= 0 ? `+$${n.toFixed(2)}` : `-$${Math.abs(n).toFixed(2)}`;
  const pnlCol = (n) => n > 0 ? 'var(--green)' : n < 0 ? 'var(--red)' : 'inherit';

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <div className="modal-handle" />
        <div className="modal-title">Sell Position</div>
        <div className="modal-sub">Exit at current market price</div>
        <div className="modal-q" style={{ marginBottom: 16 }}>{trade.q}</div>

        {loading ? (
          <div style={{ textAlign: 'center', padding: '20px 0', color: 'var(--g3)' }}>
            Fetching current price...
          </div>
        ) : value ? (
          <>
            {/* Position breakdown */}
            <div className="sell-breakdown">
              <div className="sell-row">
                <span className="sell-label">Your position</span>
                <span className="sell-val">
                  {value.shares?.toFixed(1)} <span style={{ opacity: 0.6 }}>
                    {trade.side.toUpperCase()} shares
                  </span>
                </span>
              </div>
              <div className="sell-row">
                <span className="sell-label">Entry price</span>
                <span className="sell-val">{(value.entry_price * 100).toFixed(1)}¢</span>
              </div>
              <div className="sell-row">
                <span className="sell-label">Current price</span>
                <span className="sell-val" style={{
                  color: value.current_price > value.entry_price ? 'var(--green)'
                       : value.current_price < value.entry_price ? 'var(--red)'
                       : 'inherit'
                }}>
                  {(value.current_price * 100).toFixed(1)}¢
                  <span style={{ fontSize: 10, opacity: 0.6, marginLeft: 4 }}>
                    ({value.current_price > value.entry_price ? '▲' : value.current_price < value.entry_price ? '▼' : '—'})
                  </span>
                </span>
              </div>
              <div className="sell-divider" />
              <div className="sell-row">
                <span className="sell-label">You paid</span>
                <span className="sell-val">${value.entry_value?.toFixed(2)}</span>
              </div>
              <div className="sell-row">
                <span className="sell-label">You receive</span>
                <span className="sell-val" style={{ fontWeight: 700 }}>
                  ${value.current_value?.toFixed(2)}
                </span>
              </div>
              <div className="sell-row">
                <span className="sell-label">P&amp;L</span>
                <span className="sell-val" style={{ fontWeight: 700, color: pnlCol(value.unrealized_pnl) }}>
                  {fmt(value.unrealized_pnl)}
                  <span style={{ fontSize: 10, opacity: 0.7, marginLeft: 4 }}>
                    ({value.pnl_pct >= 0 ? '+' : ''}{value.pnl_pct?.toFixed(1)}%)
                  </span>
                </span>
              </div>
            </div>

            {error && (
              <div style={{ color: 'var(--red)', fontSize: 12, textAlign: 'center', margin: '8px 0' }}>
                {error}
              </div>
            )}

            <button className="modal-cta" onClick={handleSell} disabled={selling}>
              {selling ? 'Selling...' : `Sell for $${value.current_value?.toFixed(2)}`}
            </button>
            <button className="chip-btn" onClick={onClose}
              style={{ width: '100%', marginTop: 8, opacity: 0.6 }}>
              Keep position
            </button>
          </>
        ) : (
          <div style={{ textAlign: 'center', color: 'var(--red)', padding: '12px 0' }}>
            Could not load position value.
          </div>
        )}
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function BetsPage() {
  const [trades, setTrades]       = useState([]);
  const [wallet, setWallet]       = useState(null);
  const [loading, setLoading]     = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [sellTarget, setSellTarget] = useState(null); // trade to sell
  const { showAchievement }       = useAchievement();
  const { haptic }                = useTelegram();
  const { walletAddress }         = useAuth();
  // FIX: track which achievement IDs have already been shown this session
  // so they don't pop up again on every refresh/load call.
  const shownAchievements = useRef(new Set());

  const load = async (showRefresh = false) => {
    if (showRefresh) setRefreshing(true);
    try {
      const [t, w] = await Promise.all([getTrades(), getWallet()]);
      setTrades(t);
      setWallet(w);
      if (t.length > 0) {
        const ach = await getAchievements();
        const milestones = [
          { count: 1,  id: 'first' },
          { count: 10, id: 'paper' },
          { count: 50, id: 'whale' },
        ];
        for (const { count, id } of milestones) {
          if (t.length >= count && !shownAchievements.current.has(id)) {
            const a = ach.find(x => x.id === id && x.earned);
            if (a) {
              shownAchievements.current.add(id);
              showAchievement(a);
              break; // show one at a time — don't stack popups
            }
          }
        }
      }
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    if (walletAddress) load();
  }, [walletAddress]);

  const handleSellConfirm = async (tradeId) => {
    haptic?.medium?.();
    await sellTrade(tradeId);
    haptic?.success?.();
    await load(); // reload balance + trades
  };

  const fmt      = (n) => n >= 0 ? `+$${n.toFixed(2)}` : `-$${Math.abs(n).toFixed(2)}`;
  const pnlClass = (n) => n > 0 ? 'pos' : n < 0 ? 'neg' : 'flat';

  const openTrades   = trades.filter(t => t.status === 'open');
  const closedTrades = trades.filter(t => t.status === 'closed');
  // Use counts from wallet summary (already mode-aware from backend)
  const wins   = wallet?.wins   ?? closedTrades.filter(t => (t.pnl || 0) > 0).length;
  const losses = wallet?.losses ?? closedTrades.filter(t => (t.pnl || 0) < 0).length;

  const resultBadge = (t) => {
    if (t.result === 'WIN')        return <span className="result-badge win">WIN</span>;
    if (t.result === 'LOSS')       return <span className="result-badge loss">LOSS</span>;
    if (t.result === 'SOLD')       return <span className="result-badge sold">SOLD</span>;
    if (t.result === 'EXPIRED')    return <span className="result-badge flat">EXPIRED</span>;
    if (t.result === 'BREAK_EVEN') return <span className="result-badge flat">EVEN</span>;
    return null;
  };

  return (
    <AuthGate>
      <div className="app">
        <div className="header">
          <div className="header-logo">My Bets</div>
          <div className="header-right">
            <button className="chip-btn" onClick={() => load(true)}
              disabled={refreshing} style={{ fontSize: 11 }}>
              {refreshing ? '⟳ Checking...' : '⟳ Refresh'}
            </button>
            <div className="live-pill"><span className="live-dot" />Paper</div>
          </div>
        </div>

        <div className="scroll">
          {/* ── Wallet Stats ── */}
          <div className="bets-stats fu d1">
            <div className="stat-card">
              <span className="stat-label">Balance</span>
              <span className="stat-val">${wallet?.balance?.toFixed(0) ?? '—'}</span>
            </div>
            <div className="stat-card">
              <span className="stat-label">P&amp;L</span>
              <span className={`stat-val ${wallet ? pnlClass(wallet.pnl) : ''}`}>
                {wallet ? fmt(wallet.pnl) : '—'}
              </span>
            </div>
            <div className="stat-card">
              <span className="stat-label">Trades</span>
              <span className="stat-val">{wallet?.trades ?? '—'}</span>
            </div>
            <div className="stat-card">
              <span className="stat-label">W / L</span>
              <span className="stat-val">
                <span style={{ color: 'var(--green)' }}>{wins}</span>
                {' / '}
                <span style={{ color: 'var(--red)' }}>{losses}</span>
              </span>
            </div>
          </div>

          {loading ? (
            <div className="empty">
              <div className="empty-icon">⟳</div>
              <div className="empty-text">Loading trades...</div>
            </div>
          ) : trades.length === 0 ? (
            <div className="empty">
              <div className="empty-icon">◇</div>
              <div className="empty-text">No trades yet. Go to the Feed to place your first paper trade.</div>
            </div>
          ) : (
            <>
              {/* ── Open Positions ── */}
              {openTrades.length > 0 && (
                <>
                  <div className="sec-lbl fu d2">
                    <span className="sec-t">Open Positions</span>
                    <span className="sec-t">{openTrades.length} active</span>
                  </div>
                  {openTrades.map((t, i) => {
                    const unrealized = t.unrealizedPnl ?? 0;
                    return (
                      <div key={t.id} className={`trade-item fu d${Math.min(i + 3, 6)}`}>
                        <div className={`trade-side-badge ${t.side}`}>{t.side.toUpperCase()}</div>
                        <div className="trade-info">
                          <div className="trade-q">{t.q}</div>
                          <div className="trade-meta">
                            ${t.amount.toFixed(2)} · {(t.price * 100).toFixed(0)}¢ entry
                            {t.currentPrice != null && (
                              <span style={{
                                marginLeft: 6,
                                color: t.currentPrice > t.price ? 'var(--green)'
                                     : t.currentPrice < t.price ? 'var(--red)'
                                     : 'inherit'
                              }}>
                                → {(t.currentPrice * 100).toFixed(0)}¢ now
                              </span>
                            )}
                          </div>
                        </div>
                        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4 }}>
                          <div className={`trade-pnl ${pnlClass(unrealized)}`}>
                            {fmt(unrealized)}
                          </div>
                          <button
                            className="sell-btn"
                            onClick={() => { haptic?.light?.(); setSellTarget(t); }}
                          >
                            Sell
                          </button>
                        </div>
                      </div>
                    );
                  })}
                  <div style={{ fontSize: 11, color: 'var(--g3)', textAlign: 'center', padding: '4px 0 12px', fontFamily: 'DM Mono, monospace' }}>
                    Positions auto-settle when Polymarket resolves · or sell any time
                  </div>
                </>
              )}

              {/* ── Closed Trades ── */}
              {closedTrades.length > 0 && (
                <>
                  <div className="sec-lbl fu d3">
                    <span className="sec-t">Closed Trades</span>
                    <span className="sec-t">
                      <span style={{ color: 'var(--green)' }}>{wins}W</span>
                      {' · '}
                      <span style={{ color: 'var(--red)' }}>{losses}L</span>
                    </span>
                  </div>
                  {closedTrades.map((t, i) => (
                    <div key={t.id} className={`trade-item fu d${Math.min(i + 3, 6)}`}>
                      <div className={`trade-side-badge ${t.side}`}>{t.side.toUpperCase()}</div>
                      <div className="trade-info">
                        <div className="trade-q">{t.q}</div>
                        <div className="trade-meta">
                          ${t.amount.toFixed(2)} · {(t.price * 100).toFixed(0)}¢ entry · closed
                        </div>
                      </div>
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 2 }}>
                        {resultBadge(t)}
                        <div className={`trade-pnl ${pnlClass(t.pnl || 0)}`}>
                          {t.pnl != null ? fmt(t.pnl) : '—'}
                        </div>
                      </div>
                    </div>
                  ))}
                </>
              )}
            </>
          )}
        </div>

        <Navbar active="bets" />
      </div>

      {/* Sell confirmation modal */}
      {sellTarget && (
        <SellModal
          trade={sellTarget}
          onConfirm={handleSellConfirm}
          onClose={() => setSellTarget(null)}
        />
      )}
    </AuthGate>
  );
}
