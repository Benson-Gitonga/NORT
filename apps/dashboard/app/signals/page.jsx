'use client';
import React, { useEffect, useState } from 'react';
import { getSignals } from '@/lib/api';
import Navbar from '@/components/Navbar';
import AuthGate from '@/components/AuthGate';
import Header from '@/components/Header';
import FeedCard from '@/components/FeedCard';
import SkeletonCard from '@/components/SkeletonCard';
import TradeModal from '@/components/TradeModal';
import { useRequireAuth } from '@/hooks/useAuthGuard';

const FILTERS = ['all', 'hot', 'warm', 'cool'];

export default function SignalsPage() {
  const [signals, setSignals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter]   = useState('all');
  const [tradeSignal, setTradeSignal] = useState(null);
  const [tradeSide,   setTradeSide]   = useState('yes');

  // ✅ Auth guard for trade actions — shows modal if unauthenticated
  const { requireAuth, AuthModal } = useRequireAuth();

  useEffect(() => {
    setLoading(true);
    getSignals(filter)
      .then(setSignals)
      .catch(() => setSignals([]))
      .finally(() => setLoading(false));
  }, [filter]);

  // ✅ FIXED: was a no-op stub `() => {}` — now properly guards and opens trade modal
  const handleTrade = (signal, side) => {
    requireAuth({
      action:    'trade',
      message:   'Connect your wallet to place paper trades on live signals.',
      onSuccess: () => {
        setTradeSignal(signal);
        setTradeSide(side || 'yes');
      },
    });
  };

  return (
    // ✅ softGate: signals are public, trade actions are protected
    <AuthGate softGate>
      <div className="app">
        <Header title="SIGNALS" hideLogo={true} />

        <div className="app-scroll">
          <div className="page-header" style={{ marginBottom: '32px' }}>
            <div
              className="page-title"
              style={{ fontFamily: 'Syne', fontWeight: 800, fontSize: '32px', letterSpacing: '-1px' }}
            >
              SIGNALS
            </div>
          </div>

          <div className="filter-row fu d1" style={{ marginBottom: '24px' }}>
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

          <div className="signals-list">
            {loading ? (
              [1, 2, 3].map(i => <SkeletonCard key={i} />)
            ) : signals.length === 0 ? (
              <div className="empty fu d2">
                <div className="empty-icon">◇</div>
                <div className="empty-text">No signals in this category</div>
              </div>
            ) : (
              signals.map((sig, i) => (
                <FeedCard
                  key={sig.id}
                  data={sig}
                  index={i}
                  onTrade={handleTrade}
                />
              ))
            )}
          </div>
        </div>

        <Navbar active="signals" />

        {/* Auth modal — shown when unauthenticated user clicks trade */}
        {AuthModal}

        {/* Trade modal — shown when authenticated user clicks trade */}
        {tradeSignal && (
          <TradeModal
            signal={tradeSignal}
            initialSide={tradeSide}
            onClose={() => setTradeSignal(null)}
            onSuccess={() => setTradeSignal(null)}
          />
        )}
      </div>
    </AuthGate>
  );
}
