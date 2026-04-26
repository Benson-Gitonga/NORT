'use client';
import React from 'react';
import { useState, useEffect } from 'react';
import Link from 'next/link';
import { getSignals, getWallet } from '@/lib/api';
import { useTelegram } from '@/hooks/useTelegram';
import AuthGate from '@/components/AuthGate';
import Header from '@/components/Header';
import FeedCard from '@/components/FeedCard';
import Navbar from '@/components/Navbar';
import TradeModal from '@/components/TradeModal';
import SkeletonCard from '@/components/SkeletonCard';

const FILTERS   = ['all', 'hot', 'warm', 'cool'];
const CATEGORIES = [
  { id: 'crypto', label: 'Crypto' },
  { id: 'sports', label: 'Sports' },
];

export default function FeedPage() {
  const { user } = useTelegram();
  const [signals, setSignals]         = useState([]);
  const [loading, setLoading]         = useState(true);
  const [category, setCategory]       = useState('crypto');
  const [filter, setFilter]           = useState('all');
  const [tradeSignal, setTradeSignal] = useState(null);
  const [tradeSide, setTradeSide]     = useState('yes');
  const [toast, setToast]             = useState(null);
  const [wallet, setWallet]           = useState({ balance: 0, pnl: 0, winRate: 0 });

  // Fetch wallet balance from backend
  useEffect(() => {
    getWallet()
      .then(setWallet)
      .catch(() => {});
  }, []);

  // Fetch signals whenever filter or category changes
  useEffect(() => {
    setLoading(true);
    getSignals(filter, category)
      .then(setSignals)
      .catch(() => setSignals([]))
      .finally(() => setLoading(false));
  }, [filter, category]);

  const showToast = (msg) => { setToast(msg); setTimeout(() => setToast(null), 2200); };
  const handleTrade = (signal, side) => { setTradeSignal(signal); setTradeSide(side); };
  const initials = user?.firstName ? user.firstName.slice(0, 2).toUpperCase() : 'NJ';

  return (
    <AuthGate softGate>
      <div className="app">

        <Header hideLogo={true} />

        <div className="app-scroll">
          
          {/* WALLET BALANCE CARD */}
          <div className="wallet-balance-card">
            <div className="wallet-card-left">
              <div>
                <div className="wallet-label">WALLET BALANCE:</div>
                <div className="wallet-val-large">$ {wallet.balance.toLocaleString()}</div>
              </div>
              
              <div className="wallet-stats-row">
                <div className="wallet-stat-box">
                  <div className="stat-box-label">Win Rate:</div>
                  <div className="stat-box-val">{wallet.winRate}%</div>
                </div>
                <div className="wallet-stat-box">
                  <div className="stat-box-label">P&L:</div>
                  <div className="stat-box-val" style={{ color: '#34C07F' }}>
                    + ${wallet.pnl.toLocaleString()}
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div style={{ marginBottom: '24px' }}>
            <div className="page-title" style={{ fontFamily: 'Syne', fontWeight: 800, fontSize: '32px', letterSpacing: '-1px' }}>FEED</div>
            
            <div style={{ display: 'flex', gap: '8px', marginTop: '16px' }}>
              {FILTERS.map(f => (
                <button
                  key={f}
                  className={`filter-tab ${filter === f ? 'on' : ''}`}
                  onClick={() => setFilter(f)}
                >
                  {f.charAt(0).toUpperCase() + f.slice(1)}
                </button>
              ))}
            </div>

            <div style={{ display: 'flex', gap: '8px', marginTop: '12px' }}>
              {CATEGORIES.map(c => (
                <button
                  key={c.id}
                  className={`filter-tab ${category === c.id ? 'on' : ''}`}
                  style={{ borderRadius: '8px', padding: '6px 12px' }}
                  onClick={() => setCategory(c.id)}
                >
                  {c.label}
                </button>
              ))}
            </div>
          </div>

          {/* Card grid */}
          <div className="feed-list">
            {loading
              ? [1,2,3,4,5,6].map(i => <SkeletonCard key={i} />)
              : signals.map((sig, i) => (
                  <FeedCard
                    key={sig.id}
                    data={sig}
                    index={i}
                    onTrade={handleTrade}
                  />
                ))
            }
          </div>

          {!loading && signals.length === 0 && (
            <div className="empty">
              <div className="empty-icon">◇</div>
              <div className="empty-text">No signals in this category</div>
            </div>
          )}
        </div>

        <Navbar active="feed" />

        {tradeSignal && (
          <TradeModal
            signal={tradeSignal}
            initialSide={tradeSide}
            onClose={() => setTradeSignal(null)}
            onSuccess={() => showToast('Paper trade placed ✓')}
          />
        )}

        {toast && <div className="toast">{toast}</div>}
      </div>
    </AuthGate>
  );
}
