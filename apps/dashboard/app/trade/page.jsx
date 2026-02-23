'use client';
import React from 'react';
import { useState, useEffect } from 'react';
import { getTrades, getWallet, commitTrade, getAchievements } from '@/lib/api';
import { useAchievement } from '@/components/AchievementContext';
import AuthGate from '@/components/AuthGate';
import Navbar from '@/components/Navbar';

export default function BetsPage() {
  const [trades, setTrades]   = useState([]);
  const [wallet, setWallet]   = useState(null);
  const [loading, setLoading] = useState(true);
  const [prevTrades, setPrevTrades] = useState(0);
  const [checkedInitial, setCheckedInitial] = useState(false);
  const { showAchievement } = useAchievement();

  useEffect(() => {
    Promise.all([getTrades(), getWallet()])
      .then(([t, w]) => { 
        setTrades(t); 
        setWallet(w); 
        setPrevTrades(t.length);
        setCheckedInitial(true);
      })
      .finally(() => setLoading(false));
  }, []);

  const checkAchievements = async (currentTrades) => {
    const ach = await getAchievements();
    
    if (currentTrades >= 1) {
      const first = ach.find(a => a.id === 'first' && a.earned);
      if (first) showAchievement(first);
    }
    if (currentTrades >= 10) {
      const paper = ach.find(a => a.id === 'paper' && a.earned);
      if (paper) showAchievement(paper);
    }
    if (currentTrades >= 50) {
      const whale = ach.find(a => a.id === 'whale' && a.earned);
      if (whale) showAchievement(whale);
    }
  };

  useEffect(() => {
    if (checkedInitial && trades.length > 0) {
      checkAchievements(trades.length);
    }
  }, [trades, checkedInitial]);

  const onCommit = async (id) => {
    const r = await commitTrade(id);
    if (r.ok) {
      const t = await getTrades();
      const w = await getWallet();
      setTrades(t);
      setWallet(w);
      setTimeout(() => checkAchievements(t.length), 500);
    }
  };

  const fmt = (n) => (n >= 0 ? `+$${n.toFixed(2)}` : `-$${Math.abs(n).toFixed(2)}`);
  const pnlClass = (n) => (n > 0 ? 'pos' : n < 0 ? 'neg' : 'flat');

  return (
    <AuthGate>
      <div className="app">
        {/* Header */}
        <div className="header">
          <div className="header-logo">My Bets</div>
          <div className="header-right">
            <div className="live-pill">
              <span className="live-dot" />
              Paper
            </div>
          </div>
        </div>

        <div className="scroll">
          {/* Wallet stats */}
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
          </div>

          {/* Section label */}
          <div className="sec-lbl fu d2">
            <span className="sec-t">Open Positions</span>
            <span className="sec-t">{trades.filter(t => t.status === 'open').length} active</span>
          </div>

          {/* Trade list */}
          {loading ? (
            <div className="empty"><div className="empty-icon">⟳</div><div className="empty-text">Loading trades...</div></div>
          ) : trades.length === 0 ? (
            <div className="empty">
              <div className="empty-icon">◇</div>
              <div className="empty-text">No trades yet. Place your first paper trade.</div>
            </div>
          ) : (
            <div style={{ paddingBottom: 8 }}>
              {trades.map((t, i) => (
                <div key={t.id} className={`trade-item fu d${Math.min(i + 3, 6)}`}>
                  <div className={`trade-side-badge ${t.side}`}>
                    {t.side.toUpperCase()}
                  </div>
                  <div className="trade-info">
                    <div className="trade-q">{t.q}</div>
                    <div className="trade-meta">
                      ${t.amount} · {(t.price * 100).toFixed(0)}¢ entry · {t.status}
                    </div>
                  </div>
                  <div className={`trade-pnl ${pnlClass(t.pnl)}`}>
                    {t.pnl !== 0 ? fmt(t.pnl) : '—'}
                  </div>
                  {t.status === 'open' && !t.txHash ? (
                    <button
                      onClick={() => onCommit(t.id)}
                      style={{ marginLeft: 8 }}
                      className="chip-btn"
                    >
                      Commit
                    </button>
                  ) : null}
                </div>
              ))}
            </div>
          )}
        </div>

        <Navbar active="bets" />
      </div>
    </AuthGate>
  );
}
