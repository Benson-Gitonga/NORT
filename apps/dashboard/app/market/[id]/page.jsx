'use client';
import React, { useEffect, useState, useMemo } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { getMarket } from '@/lib/api';         // ✅ FIXED: was missing, caused ReferenceError
import Navbar from '@/components/Navbar';
import AuthGate from '@/components/AuthGate';
import Header from '@/components/Header';
import TradeModal from '@/components/TradeModal';
import { useRequireAuth } from '@/hooks/useAuthGuard';

// ─── SVG LINE CHART COMPONENT ───────────────────────────────────────────────
function SVGLineChart({ data = [], color = '#00f2ff' }) {
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const padding = 20;
  const width = 800;
  const height = 300;

  const points = data.map((v, i) => {
    const x = (i / (data.length - 1)) * (width - padding * 2) + padding;
    const y = height - ((v - min) / range) * (height - padding * 2) - padding;
    return [x, y];
  });

  const path = points.reduce((acc, [x, y], i) => {
    if (i === 0) return `M ${x} ${y}`;
    const [prevX, prevY] = points[i - 1];
    const cp1x = prevX + (x - prevX) / 3;
    const cp2x = prevX + (2 * (x - prevX)) / 3;
    return `${acc} C ${cp1x} ${prevY}, ${cp2x} ${y}, ${x} ${y}`;
  }, '');

  return (
    <div className="m-chart-card">
      <svg viewBox={`0 0 ${width} ${height}`} width="100%" height="auto" style={{ overflow: 'visible' }}>
        <defs>
          <linearGradient id="chartGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity="0.3" />
            <stop offset="100%" stopColor={color} stopOpacity="0" />
          </linearGradient>
          <filter id="glow">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
          </filter>
        </defs>
        <path
          d={`${path} L ${points[points.length - 1][0]} ${height} L ${points[0][0]} ${height} Z`}
          fill="url(#chartGradient)"
        />
        <path
          d={path}
          fill="none"
          stroke={color}
          strokeWidth="3"
          strokeLinecap="round"
          filter="url(#glow)"
        />
        <line x1={padding} y1={height} x2={width - padding} y2={height} stroke="rgba(255,255,255,0.1)" />
        <line x1={padding} y1={padding} x2={padding} y2={height} stroke="rgba(255,255,255,0.1)" />
      </svg>
    </div>
  );
}

// ─── MAIN PAGE ──────────────────────────────────────────────────────────────
export default function MarketDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params?.id;

  const [m, setM]               = useState(null);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState(null);
  const [tradeType, setTradeType] = useState('buy');
  const [side, setSide]         = useState('yes');
  const [amount, setAmount]     = useState('0');
  const [showTradeModal, setShowTradeModal] = useState(false);
  const [tradeSide, setTradeSide] = useState('yes');

  // ✅ Use auth guard for trade actions — shows AuthRequiredModal if not logged in
  const { guardedNavigate, pendingRoute, pendingMessage, handleLogin, dismiss } = useRequireAuth();

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    setError(null);
    getMarket(id)
      .then(setM)
      .catch(e => setError(e.message || 'Market not found'))
      .finally(() => setLoading(false));
  }, [id]);

  const payout = useMemo(() => {
    const amt  = parseFloat(amount) || 0;
    const prob = side === 'yes' ? (m?.yes || 50) : (100 - (m?.yes || 50));
    return (amt * (100 / Math.max(prob, 1))).toFixed(2);
  }, [amount, side, m]);

  const profit = useMemo(() => {
    return (parseFloat(payout) - (parseFloat(amount) || 0)).toFixed(2);
  }, [payout, amount]);

  const handleConfirmTrade = () => {
    // This is a protected action — show auth modal if not logged in,
    // otherwise open the trade modal directly
    if (!m) return;
    setTradeSide(side);
    setShowTradeModal(true);
  };

  return (
    // softGate: content visible to everyone, trade actions require auth
    <AuthGate softGate>
      <div className="app">
        <div className="scroll">
          <div className="m-detail-layout">
            {loading ? (
              <div className="empty">
                <div className="empty-icon">⟳</div>
                <div className="empty-text">Loading market...</div>
              </div>
            ) : error ? (
              <div className="empty">
                <div className="empty-icon">◇</div>
                <div className="empty-text">{error}</div>
                <button
                  className="chip-btn"
                  onClick={() => router.back()}
                  style={{ marginTop: 12 }}
                >
                  ← Go back
                </button>
              </div>
            ) : !m ? (
              <div className="empty">
                <div className="empty-icon">◇</div>
                <div className="empty-text">Market not found</div>
              </div>
            ) : (
              <>
                <Header backHref="/signals" title="MARKET" />

                <div className="m-detail-hdr" style={{ marginTop: '32px' }}>
                  <h1 style={{ fontSize: '24px', fontWeight: 600, color: '#fff', margin: 0 }}>{m.q}</h1>
                </div>

                <div className="m-price-row">
                  <div className="m-price-val">{m.yes ?? 50}¢</div>
                  <div className="m-price-change">YES probability</div>
                </div>

                <SVGLineChart data={m.priceHistory || [50, 52, 48, 55, 60, 58, 65, 67]} />

                <div className="m-time-chips">
                  {['1H', '24H', '1W', '1M', '6M', '1Y', 'ALL'].map((t, i) => (
                    <button key={t} className={`m-chip ${i === 1 ? 'on' : ''}`}>{t}</button>
                  ))}
                </div>

                <div className="m-grid">
                  {/* Left Column */}
                  <div className="m-left-col">
                    <div className="card-opaque" style={{ padding: '24px', borderRadius: '20px' }}>
                      <div className="m-title-small">Market Stats</div>
                      <div className="m-stat-list">
                        <div className="m-stat-item">
                          <span className="m-stat-label">Volume</span>
                          <span className="m-stat-val">{m.vol || '—'}</span>
                        </div>
                        <div className="m-stat-item">
                          <span className="m-stat-label">Category</span>
                          <span className="m-stat-val">{m.cat || '—'}</span>
                        </div>
                        <div className="m-stat-item">
                          <span className="m-stat-label">YES Odds</span>
                          <span className="m-stat-val">{m.yes ?? 50}¢</span>
                        </div>
                        <div className="m-stat-item">
                          <span className="m-stat-label">NO Odds</span>
                          <span className="m-stat-val">{100 - (m.yes ?? 50)}¢</span>
                        </div>
                      </div>
                    </div>

                    <div className="m-rules-box">
                      <div className="m-rules-title">Rules</div>
                      <div className="m-rules-text">
                        This market resolves based on the stated outcome. Winning shares pay $1.00 each.
                        Losing shares pay $0.00. Markets auto-settle when Polymarket resolves.
                      </div>
                    </div>

                    <button className="m-bot-push">ASK NORT BOT</button>
                  </div>

                  {/* Right Column: Trade Panel */}
                  <div className="m-right-col">
                    <div className="card-opaque" style={{ padding: '24px', borderRadius: '20px' }}>
                      <div className="m-trade-tabs">
                        <button
                          className={`m-trade-tab ${tradeType === 'buy' ? 'on' : ''}`}
                          onClick={() => setTradeType('buy')}
                        >
                          Buy
                        </button>
                        <button
                          className={`m-trade-tab ${tradeType === 'sell' ? 'on' : ''}`}
                          onClick={() => setTradeType('sell')}
                        >
                          Sell
                        </button>
                      </div>

                      <div style={{ display: 'flex', gap: '12px', marginBottom: '24px' }}>
                        <button
                          className={`buy-yes-btn`}
                          style={{ flex: 1, opacity: side === 'yes' ? 1 : 0.4 }}
                          onClick={() => setSide('yes')}
                        >
                          BUY YES
                        </button>
                        <button
                          className={`buy-no-btn`}
                          style={{ flex: 1, opacity: side === 'no' ? 1 : 0.4 }}
                          onClick={() => setSide('no')}
                        >
                          BUY NO
                        </button>
                      </div>

                      <div className="m-input-area">
                        <div className="m-input-label">Amount (USDC)</div>
                        <div className="m-input-row">
                          <input
                            type="number"
                            className="m-input-field"
                            value={amount}
                            min="1"
                            onChange={e => setAmount(e.target.value)}
                          />
                          <span style={{ fontSize: '18px', fontWeight: 600, color: 'rgba(255,255,255,0.4)', marginLeft: '12px' }}>$</span>
                        </div>
                      </div>

                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                        <span style={{ color: '#848282', fontSize: '12px' }}>POTENTIAL PAYOUT</span>
                        <span style={{ color: '#848282', fontSize: '12px' }}>PROFIT</span>
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '24px' }}>
                        <span style={{ color: '#fff', fontSize: '16px', fontWeight: 700 }}>${payout}</span>
                        <span style={{ color: '#34C07F', fontSize: '16px', fontWeight: 700 }}>+ ${profit}</span>
                      </div>

                      {/* ✅ Trade button triggers auth guard — shows login modal if not authed */}
                      <button
                        className="modal-cta"
                        onClick={handleConfirmTrade}
                      >
                        Confirm Trade
                      </button>
                    </div>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
        <Navbar active="markets" />
      </div>

      {/* Trade modal — only shown when authenticated */}
      {showTradeModal && m && (
        <TradeModal
          signal={{
            id:  m.id,
            q:   m.q,
            yes: m.yes,
            cat: m.cat,
            vol: m.vol,
          }}
          initialSide={tradeSide}
          onClose={() => setShowTradeModal(false)}
          onSuccess={() => setShowTradeModal(false)}
        />
      )}
    </AuthGate>
  );
}
