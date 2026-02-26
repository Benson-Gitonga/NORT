'use client';
import React from 'react';
import { useState, useEffect } from 'react';
import { getTrades, getWallet, getAchievements } from '@/lib/api';
import { useAchievement } from '@/components/AchievementContext';
import AuthGate from '@/components/AuthGate';
import Navbar from '@/components/Navbar';

export default function BetsPage() {
  const [trades, setTrades]   = useState([]);
  const [wallet, setWallet]   = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const { showAchievement } = useAchievement();

  const load = async (showRefresh = false) => {
    if (showRefresh) setRefreshing(true);
    try {
      const [t, w] = await Promise.all([getTrades(), getWallet()]);
      setTrades(t);
      setWallet(w);
      // Check achievements after loading
      if (t.length > 0) {
        const ach = await getAchievements();
        if (t.length >= 1)  { const a = ach.find(x => x.id === 'first' && x.earned);   if (a) showAchievement(a); }
        if (t.length >= 10) { const a = ach.find(x => x.id === 'paper' && x.earned);   if (a) showAchievement(a); }
        if (t.length >= 50) { const a = ach.find(x => x.id === 'whale' && x.earned);   if (a) showAchievement(a); }
      }
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => { load(); }, []);

  const fmt      = (n) => n >= 0 ? `+$${n.toFixed(2)}` : `-$${Math.abs(n).toFixed(2)}`;
  const pnlClass = (n) => n > 0 ? 'pos' : n < 0 ? 'neg' : 'flat';

  const openTrades   = trades.filter(t => t.status === 'open');
  const closedTrades = trades.filter(t => t.status === 'closed' || t.status === 'CLOSED');
  const wins         = closedTrades.filter(t => (t.pnl || 0) > 0);
  const losses       = closedTrades.filter(t => (t.pnl || 0) < 0);

  const resultBadge = (t) => {
    if (t.status !== 'closed' && t.status !== 'CLOSED') return null;
    if ((t.pnl || 0) > 0)  return <span className="result-badge win">WIN</span>;
    if ((t.pnl || 0) < 0)  return <span className="result-badge loss">LOSS</span>;
    return <span className="result-badge flat">EVEN</span>;
  };

  return (
    <AuthGate>
      <div className="app">
        <div className="header">
          <div className="header-logo">My Bets</div>
          <div className="header-right">
            <button
              className="chip-btn"
              onClick={() => load(true)}
              disabled={refreshing}
              style={{ fontSize: 11 }}
            >
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
                <span style={{ color: 'var(--green)' }}>{wins.length}</span>
                {' / '}
                <span style={{ color: 'var(--red)' }}>{losses.length}</span>
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
                  <div style={{ paddingBottom: 4 }}>
                    {openTrades.map((t, i) => (
                      <div key={t.id} className={`trade-item fu d${Math.min(i + 3, 6)}`}>
                        <div className={`trade-side-badge ${t.side}`}>{t.side.toUpperCase()}</div>
                        <div className="trade-info">
                          <div className="trade-q">{t.q}</div>
                          <div className="trade-meta">
                            ${t.amount?.toFixed(2)} · {(t.price * 100).toFixed(0)}¢ entry · waiting for resolution
                          </div>
                        </div>
                        <div className="trade-pnl flat">pending</div>
                      </div>
                    ))}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--g3)', textAlign: 'center', padding: '4px 0 12px', fontFamily: 'DM Mono, monospace' }}>
                    Trades settle automatically when Polymarket resolves the market
                  </div>
                </>
              )}

              {/* ── Closed Trades (wins/losses) ── */}
              {closedTrades.length > 0 && (
                <>
                  <div className="sec-lbl fu d3">
                    <span className="sec-t">Closed Trades</span>
                    <span className="sec-t">
                      <span style={{ color: 'var(--green)' }}>{wins.length}W</span>
                      {' · '}
                      <span style={{ color: 'var(--red)' }}>{losses.length}L</span>
                    </span>
                  </div>
                  <div style={{ paddingBottom: 8 }}>
                    {closedTrades.map((t, i) => (
                      <div key={t.id} className={`trade-item fu d${Math.min(i + 3, 6)}`}>
                        <div className={`trade-side-badge ${t.side}`}>{t.side.toUpperCase()}</div>
                        <div className="trade-info">
                          <div className="trade-q">{t.q}</div>
                          <div className="trade-meta">
                            ${t.amount?.toFixed(2)} · {(t.price * 100).toFixed(0)}¢ entry · closed
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
                  </div>
                </>
              )}
            </>
          )}
        </div>

        <Navbar active="bets" />
      </div>
    </AuthGate>
  );
}
