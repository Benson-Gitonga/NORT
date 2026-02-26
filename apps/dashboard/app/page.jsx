'use client';
import React from 'react';
import { useState, useEffect } from 'react';
import Link from 'next/link';
import { getSignals } from '@/lib/api';
import { useTelegram } from '@/hooks/useTelegram';
import AuthGate from '@/components/AuthGate';
import FeedCard from '@/components/FeedCard';
import Navbar from '@/components/Navbar';
import TradeModal from '@/components/TradeModal';
import ChatSheet from '@/components/ChatSheet';
import SkeletonCard from '@/components/SkeletonCard';

const FILTERS = ['all', 'hot', 'warm', 'cool'];

export default function FeedPage() {
  const { user } = useTelegram();
  const [signals, setSignals]         = useState([]);
  const [loading, setLoading]         = useState(true);
  const [filter, setFilter]           = useState('all');
  const [tradeSignal, setTradeSignal] = useState(null);
  const [tradeSide, setTradeSide]     = useState('yes');
  const [chatSignal, setChatSignal]   = useState(null);
  const [toast, setToast]             = useState(null);

  useEffect(() => {
    setLoading(true);
    getSignals(filter).then(setSignals).finally(() => setLoading(false));
  }, [filter]);

  const showToast = (msg) => { setToast(msg); setTimeout(() => setToast(null), 2200); };
  const handleTrade = (signal, side) => { setTradeSignal(signal); setTradeSide(side); };
  const initials = user?.firstName ? user.firstName.slice(0, 2).toUpperCase() : 'NJ';

  return (
    <AuthGate softGate>
      <div className="app">

        {/* ── Mobile-only header ── */}
        <div className="header">
          <div className="header-logo">NORT</div>
          <div className="header-right">
            <div className="live-pill"><span className="live-dot" />Live</div>
            <Link href="/profile" className="user-av">{initials}</Link>
          </div>
        </div>

        {/* ── Main scroll area (mobile padding + desktop max-width) ── */}
        <div className="app-scroll">

          {/* Desktop page title row */}
          <div className="page-header">
            <div>
              <div className="page-title">Trending Signals</div>
              <div className="page-meta">Updated just now · {signals.length} signals</div>
            </div>
            <div className="filter-row">
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
                    onChat={setChatSignal}
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

        {/* Nav (bottom mobile / top desktop) */}
        <Navbar active="feed" />

        {/* Modals */}
        {tradeSignal && (
          <TradeModal
            signal={tradeSignal}
            initialSide={tradeSide}
            onClose={() => setTradeSignal(null)}
            onSuccess={() => showToast('Paper trade placed ✓')}
          />
        )}
        {chatSignal && (
          <ChatSheet signal={chatSignal} onClose={() => setChatSignal(null)} />
        )}

        {toast && <div className="toast">{toast}</div>}
      </div>
    </AuthGate>
  );
}
