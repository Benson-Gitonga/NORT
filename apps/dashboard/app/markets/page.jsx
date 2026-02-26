'use client';
import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { listMarkets, refreshMarkets } from '@/lib/api';
import Navbar from '@/components/Navbar';
import AuthGate from '@/components/AuthGate';

export default function MarketsPage() {
  const [items, setItems]       = useState([]);
  const [loading, setLoading]   = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError]       = useState(null);

  const load = () => {
    setLoading(true);
    setError(null);
    listMarkets()
      .then(setItems)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const onRefresh = async () => {
    setRefreshing(true);
    try {
      await refreshMarkets();
    } catch (e) {
      setError(e.message);
    } finally {
      setRefreshing(false);
      load();
    }
  };

  return (
    <AuthGate softGate>
      <div className="app">
        <div className="header">
          <div className="header-logo">Markets</div>
          <div className="header-right">
            <div className="live-pill">
              <span className="live-dot" />
              Live
            </div>
            <button onClick={onRefresh} className="chip-btn">
              {refreshing ? '⟳' : '↻'}
            </button>
          </div>
        </div>

        <div className="scroll">
          {loading ? (
            <div className="empty">
              <div className="empty-icon">⟳</div>
              <div className="empty-text">Loading markets...</div>
            </div>
          ) : error ? (
            <div className="empty">
              <div className="empty-icon">!</div>
              <div className="empty-text">Failed to load markets: {error}</div>
              <button onClick={onRefresh} className="chip-btn" style={{ marginTop: 12 }}>
                Retry
              </button>
            </div>
          ) : items.length === 0 ? (
            <div className="empty">
              <div className="empty-icon">◇</div>
              <div className="empty-text">No markets available.</div>
              <button onClick={onRefresh} className="chip-btn" style={{ marginTop: 12 }}>
                Refresh from Polymarket
              </button>
            </div>
          ) : (
            <div style={{ paddingBottom: 8 }}>
              {items.map((m, i) => (
                <Link key={m.id} href={`/market/${m.id}`}>
                  <div className={`scard fu d${Math.min(i + 2, 6)}`}>
                    <div className="scard-bar" />
                    <div className="scard-inner">
                      <div className="scard-meta">
                        <span className="scard-cat">{m.cat || 'General'}</span>
                        <span className="scard-heat">{m.vol}</span>
                      </div>
                      <div className="scard-q">{m.q}</div>
                      <div className="odds-wrap">
                        <div className="odds-bar-track">
                          <div className="odds-bar-fill" style={{ width: `${m.yes}%` }} />
                        </div>
                        <div className="odds-labels">
                          <span className="odds-yes">YES {m.yes}%</span>
                          <span className="odds-vol">NO {100 - m.yes}%</span>
                        </div>
                      </div>
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
        <Navbar active="markets" />
      </div>
    </AuthGate>
  );
}
