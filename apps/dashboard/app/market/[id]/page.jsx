'use client';
import React, { useEffect, useState, useMemo } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import Navbar from '@/components/Navbar';
import AuthGate from '@/components/AuthGate';
import Header from '@/components/Header';

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
        {/* Simple Axes */}
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
  const [m, setM] = useState(null);
  const [loading, setLoading] = useState(true);
  const [tradeType, setTradeType] = useState('buy'); // 'buy' | 'sell'
  const [side, setSide] = useState('yes'); // 'yes' | 'no'
  const [amount, setAmount] = useState('0');

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    getMarket(id).then(setM).finally(() => setLoading(false));
  }, [id]);

  const payout = useMemo(() => {
    const amt = parseFloat(amount) || 0;
    const prob = side === 'yes' ? (m?.yes || 50) : (100 - (m?.yes || 50));
    return (amt * (100 / prob)).toFixed(2);
  }, [amount, side, m]);

  const profit = useMemo(() => {
    return (parseFloat(payout) - (parseFloat(amount) || 0)).toFixed(2);
  }, [payout, amount]);

  return (
    <AuthGate>
      <div className="app">
        <div className="scroll">
          <div className="m-detail-layout">
            {loading ? (
              <div className="empty">
                <div className="empty-text">Loading market...</div>
              </div>
            ) : !m ? (
              <div className="empty">
                <div className="empty-text">Market not found</div>
              </div>
            ) : (
              <>
                <Header backHref="/signals" title="MARKET" />

                {/* Question Title */}
                <div className="m-detail-hdr" style={{ marginTop: '32px' }}>
                  <h1 style={{ fontSize: '24px', fontWeight: 600, color: '#fff', margin: 0 }}>{m.q}</h1>
                </div>

                {/* Price Display */}
                <div className="m-price-row">
                  <div className="m-price-val">{m.price || '$98,509.75'}</div>
                  <div className="m-price-change">{m.change || '+1700.254 (9.77%)'}</div>
                </div>

                {/* Functional Chart */}
                <SVGLineChart data={m.priceHistory || [50, 52, 48, 55, 60, 58, 65, 67]} />

                {/* Timechips */}
                <div className="m-time-chips">
                  {['1H', '24H', '1W', '1M', '6M', '1Y', 'ALL'].map((t, i) => (
                    <button key={t} className={`m-chip ${i === 1 ? 'on' : ''}`}>{t}</button>
                  ))}
                </div>

                <div className="m-grid">
                  {/* Left Column: Stats & Rules */}
                  <div className="m-left-col">
                    <div className="card-opaque" style={{ padding: '24px', borderRadius: '20px' }}>
                      <div className="m-title-small">Market Stats</div>
                      <div className="m-stat-list">
                        <div className="m-stat-item">
                          <span className="m-stat-label">Market Cap</span>
                          <span className="m-stat-val">239.3 trillion</span>
                        </div>
                        <div className="m-stat-item">
                          <span className="m-stat-label">Volume</span>
                          <span className="m-stat-val">24.1 trillion</span>
                        </div>
                        <div className="m-stat-item">
                          <span className="m-stat-label">Circulating Supply</span>
                          <span className="m-stat-val">116.0 million</span>
                        </div>
                        <div className="m-stat-item">
                          <span className="m-stat-label">Popularity</span>
                          <span className="m-stat-val">#1</span>
                        </div>
                      </div>
                    </div>

                    <div className="m-rules-box">
                      <div className="m-rules-title">Rules</div>
                      <div className="m-rules-text">
                        This market will resolve to "Up" if the Bitcoin price at the end of the time range specified in the title is greater than or equal to the price at the beginning of that range. Otherwise, it will resolve to "Down".
                      </div>
                    </div>

                    <button className="m-bot-push">ASK NORT BOT</button>
                  </div>

                  {/* Right Column: Trade Panel */}
                  <div className="m-right-col">
                    <div className="card-opaque" style={{ padding: '24px', borderRadius: '20px' }}>
                      <div className="m-trade-tabs">
                        <button className={`m-trade-tab ${tradeType === 'buy' ? 'on' : ''}`} onClick={() => setTradeType('buy')}>Buy</button>
                        <button className={`m-trade-tab ${tradeType === 'sell' ? 'on' : ''}`} onClick={() => setTradeType('sell')}>Sell</button>
                      </div>

                      <div style={{ display: 'flex', gap: '12px', marginBottom: '24px' }}>
                        <button className={`buy-yes-btn ${side === 'no' ? 'dimmed' : ''}`} style={{ flex: 1, opacity: side === 'yes' ? 1 : 0.4 }} onClick={() => setSide('yes')}>BUY YES</button>
                        <button className={`buy-no-btn ${side === 'yes' ? 'dimmed' : ''}`} style={{ flex: 1, opacity: side === 'no' ? 1 : 0.4 }} onClick={() => setSide('no')}>BUY NO</button>
                      </div>

                      <div className="m-input-area">
                        <div className="m-input-label">Amount</div>
                        <div className="m-input-row">
                          <input type="number" className="m-input-field" value={amount} onChange={(e) => setAmount(e.target.value)} />
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

                      <button className="modal-cta">Confirm Trade</button>
                    </div>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
        <Navbar active="markets" />
      </div>
    </AuthGate>
  );
}
