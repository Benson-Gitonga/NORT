'use client';
import React, { useEffect, useState, useMemo, useRef, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { getMarket, getMarketPriceHistory, listMarkets } from '@/lib/api';
import Navbar from '@/components/Navbar';
import AuthGate from '@/components/AuthGate';
import Header from '@/components/Header';
import TradeModal from '@/components/TradeModal';
import { useRequireAuth } from '@/hooks/useAuthGuard';

const CRYPTO_CATS = new Set(['BTC', 'ETH', 'SOL', 'XRP', 'HYPE', 'Crypto']);

const INTERVALS = [
  { label: '1D', value: '1d' },
  { label: '1W', value: '1w' },
  { label: '1M', value: '1m' },
  { label: '6M', value: '6m' },
  { label: '1Y', value: '1y' },
  { label: 'ALL', value: 'all' },
];

// ─── SVG LINE CHART ──────────────────────────────────────────────────────────
function SVGLineChart({ data = [], isLive = false }) {
  const [hoverIdx, setHoverIdx] = useState(null);
  const svgRef = useRef(null);
  const [liveData, setLiveData] = useState(data);

  useEffect(() => { setLiveData(data); }, [data]);

  useEffect(() => {
    if (!isLive || data.length < 2) return;
    setLiveData(data);
  }, [isLive, data]);

  const PL = 60, PR = 60, PT = 35, PB = 45, W = 1000, H = 380; // market-p3: increased dimensions for better spacing
  const IW = W - PL - PR;

  // market-p3: Enforce constant point count for smooth transitions
  const pts = useMemo(() => {
    const raw = isLive ? liveData : data;
    if (!raw || raw.length < 2) return [];
    
    const targetCount = 120;
    if (raw.length === targetCount) return raw;
    if (raw.length > targetCount) return raw.slice(-targetCount);
    
    // Pad start with the first value to reach targetCount
    const firstVal = raw[0];
    const padding = Array(targetCount - raw.length).fill(firstVal);
    return [...padding, ...raw];
  }, [isLive, liveData, data]);

  const handleMouseMove = useCallback(e => {
    if (!svgRef.current) return;
    const r     = svgRef.current.getBoundingClientRect();
    const ratio = (e.clientX - r.left) / r.width * W - PL;
    const idx   = Math.round((ratio / IW) * (pts.length - 1));
    setHoverIdx(Math.max(0, Math.min(pts.length - 1, idx)));
  }, [pts.length, IW, W, PL]);

  if (!pts || pts.length < 2) return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      height: 220, color: 'rgba(140,140,140,0.45)',
      fontFamily: 'DM Mono, monospace', fontSize: 12,
    }}>
      No chart data available
    </div>
  );

  const IH = H - PT - PB;

  const first    = pts[0];
  const last     = pts[pts.length - 1];
  const trend    = last >= first ? '#34C07F' : '#F87171';
  const rawMin   = Math.min(...pts);
  const rawMax   = Math.max(...pts);
  const rawRange = rawMax - rawMin;
  const pad      = Math.max(rawRange * 0.22, 4);
  const yMin     = Math.max(0,   rawMin - pad);
  const yMax     = Math.min(100, rawMax + pad);
  const yRange   = yMax - yMin || 1;

  const toX = i => (i / (pts.length - 1)) * IW + PL;
  const toY = v => H - PB - ((v - yMin) / yRange) * IH;

  const coords = pts.map((v, i) => [toX(i), toY(v)]);
  const linePath = coords.reduce((acc, [x, y], i) => {
    if (i === 0) return `M ${x.toFixed(1)} ${y.toFixed(1)}`;
    const [px, py] = coords[i - 1];
    const cp1x = (px + (x - px) * 0.55).toFixed(1);
    const cp2x = (x  - (x - px) * 0.55).toFixed(1);
    return `${acc} C ${cp1x} ${py.toFixed(1)} ${cp2x} ${y.toFixed(1)} ${x.toFixed(1)} ${y.toFixed(1)}`;
  }, '');
  const areaPath = `${linePath} L ${coords[coords.length - 1][0].toFixed(1)} ${(H - PB).toFixed(1)} L ${coords[0][0].toFixed(1)} ${(H - PB).toFixed(1)} Z`;

  const tickStep = rawRange <= 5 ? 1 : rawRange <= 12 ? 2 : rawRange <= 25 ? 5 : 10;
  const ticks = [];
  for (let t = Math.ceil(yMin / tickStep) * tickStep; t <= yMax; t += tickStep) {
    if (t >= 0 && t <= 100) ticks.push(t);
  }

  const xLabelCount = Math.min(5, pts.length);
  const xLabels = Array.from({ length: xLabelCount }, (_, i) => {
    const idx = Math.round((i / (xLabelCount - 1)) * (pts.length - 1));
    return { idx, x: toX(idx) };
  });



  const [lx, ly] = coords[coords.length - 1];
  const hp       = hoverIdx !== null ? coords[hoverIdx] : null;
  const hv       = hoverIdx !== null ? pts[hoverIdx]    : null;
  const change   = last - first;
  const pct      = first > 0 ? ((change / first) * 100).toFixed(1) : '0.0';
  const targetY  = toY(first);
  const tipX     = hp ? Math.max(30, Math.min(hp[0], W - PR - 30)) : 0;
  const tipY     = hp ? Math.max(PT + 14, hp[1] - 36)              : 0;

  return (
    <div style={{ position: 'relative', userSelect: 'none' }}>
      {/* Change badge + live indicator */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
        <span style={{
          fontFamily: 'DM Mono,monospace', fontSize: 11, fontWeight: 700,
          letterSpacing: '0.4px',
          color: change >= 0 ? '#34C07F' : '#F87171',
          background: change >= 0 ? 'rgba(52,192,127,0.1)' : 'rgba(248,113,113,0.1)',
          border: `1px solid ${change >= 0 ? 'rgba(52,192,127,0.35)' : 'rgba(248,113,113,0.35)'}`,
          borderRadius: 100, padding: '3px 12px',
        }}>
          {change >= 0 ? '▲' : '▼'} {change >= 0 ? '+' : ''}{change.toFixed(1)}¢ ({pct}%)
        </span>
        <span style={{ fontFamily: 'DM Mono,monospace', fontSize: 10, color: 'rgba(140,140,140,0.45)' }}>
          open {first}¢
        </span>
        {isLive && (
          <span style={{ display: 'flex', alignItems: 'center', gap: 5, fontFamily: 'DM Mono,monospace', fontSize: 10, color: '#34C07F' }}>
            <span style={{
              width: 6, height: 6, borderRadius: '50%', background: '#34C07F',
              display: 'inline-block', animation: 'blink 2s ease-in-out infinite',
              boxShadow: '0 0 6px rgba(52,192,127,0.8)',
            }} />
            LIVE
          </span>
        )}
      </div>

      <svg
        ref={svgRef}
        viewBox={`0 0 ${W} ${H}`}
        width="100%"
        height="auto"
        style={{ overflow: 'visible', display: 'block', cursor: 'crosshair' }}
        onMouseMove={handleMouseMove}
        onMouseLeave={() => setHoverIdx(null)}
      >
        <defs>
          <linearGradient id="area-grad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%"   stopColor={trend} stopOpacity="0.22" />
            <stop offset="75%"  stopColor={trend} stopOpacity="0.04" />
            <stop offset="100%" stopColor={trend} stopOpacity="0"    />
          </linearGradient>
          <filter id="line-glow">
            <feGaussianBlur stdDeviation="2.5" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
          </filter>
          <filter id="dot-glow">
            <feGaussianBlur stdDeviation="4" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
          </filter>
          <clipPath id="chart-clip">
            <rect x={PL} y={PT} width={IW} height={IH + 1} />
          </clipPath>
        </defs>

        {/* Y-axis grid + labels */}
        {ticks.map(t => (
          <g key={t}>
            <line x1={PL} y1={toY(t)} x2={W - PR} y2={toY(t)} stroke="rgba(255,255,255,0.055)" strokeWidth="1" strokeDasharray="4 6" />
            <text x={PL - 8} y={toY(t) + 4} textAnchor="end" fill="rgba(140,140,140,0.5)" fontSize="10" fontFamily="DM Mono,monospace">{t}¢</text>
          </g>
        ))}

        {/* X-axis baseline */}
        <line x1={PL} y1={H - PB} x2={W - PR} y2={H - PB} stroke="rgba(255,255,255,0.08)" strokeWidth="1" />

        {/* X-axis labels */}
        {xLabels.map(({ idx, x }, i) => (
          <text key={i} x={x} y={H - PB + 16} textAnchor="middle" fill="rgba(140,140,140,0.4)" fontSize="9" fontFamily="DM Mono,monospace">
            {i === 0 ? 'open' : i === xLabelCount - 1 ? 'now' : `${Math.round((idx / (pts.length - 1)) * 100)}%`}
          </text>
        ))}

        {/* Opening-price reference line (grey) */}
        <line x1={PL} y1={targetY} x2={W - PR} y2={targetY} stroke="rgba(160,160,160,0.3)" strokeWidth="1" strokeDasharray="5 5" />
        <rect x={W - PR + 4} y={targetY - 10} width={46} height={19} rx={4} fill="rgba(30,30,30,0.9)" stroke="rgba(160,160,160,0.3)" strokeWidth="1" />
        <text x={W - PR + 27} y={targetY + 3} textAnchor="middle" fill="rgba(160,160,160,0.7)" fontSize="9" fontFamily="DM Mono,monospace" fontWeight="600">OPEN</text>

        {/* Area fill + price line */}
        <g clipPath="url(#chart-clip)">
          <path className="chart-area" d={areaPath} fill="url(#area-grad)" />
          <path className="chart-path" d={linePath} fill="none" stroke={trend} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" filter="url(#line-glow)" />
        </g>
        
        {/* Reference dot for current price (only if not hovering) */}
        {!hp && <circle className="chart-dot" cx={lx} cy={ly} r="3.5" fill={trend} />}

        {/* Current price dot */}
        <circle cx={lx} cy={ly} r={isLive ? 10 : 9} fill={trend} opacity="0.14" filter="url(#dot-glow)"
          style={{ animation: isLive ? 'livePulse 2s ease-in-out infinite' : 'none' }} />
        <circle cx={lx} cy={ly} r="4.5" fill={trend} />
        <circle cx={lx} cy={ly} r="2"   fill="#000" />
        <rect   x={lx - 25} y={ly - 28} width={50} height={20} rx={5} fill="rgba(0,0,0,0.88)" stroke={trend} strokeWidth="1" strokeOpacity="0.7" />
        <text   x={lx} y={ly - 14} textAnchor="middle" fill={trend} fontSize="10" fontFamily="DM Mono,monospace" fontWeight="700">{last}¢</text>

        {/* Hover crosshair */}
        {hp && (
          <g>
            <line x1={hp[0]} y1={PT} x2={hp[0]} y2={H - PB} stroke="rgba(255,255,255,0.18)" strokeWidth="1" strokeDasharray="3 4" />
            <circle cx={hp[0]} cy={hp[1]} r="5" fill={trend} stroke="#000" strokeWidth="2" />
            <rect   x={tipX - 26} y={tipY} width={52} height={22} rx={5} fill="rgba(10,10,10,0.94)" stroke="rgba(255,255,255,0.12)" strokeWidth="1" />
            <text   x={tipX} y={tipY + 14} textAnchor="middle" fill="#fff" fontSize="11" fontFamily="DM Mono,monospace" fontWeight="600">{hv}¢</text>
          </g>
        )}
      </svg>

      <style>{`
        @keyframes livePulse { 0%,100% { r:10; opacity:.14; } 50% { r:14; opacity:.08; } }
        .chart-path { transition: d 0.6s ease-in-out; }
        .chart-area { transition: d 0.6s ease-in-out; }
        .chart-dot  { transition: all 0.6s ease-in-out; }
      `}</style>
    </div>
  );
}

// ─── MARKET STATUS BADGE ─────────────────────────────────────────────────────
function MarketStatusBadge({ yes }) {
  if (yes === null || yes === undefined) return null;

  const resolved    = yes <= 2 || yes >= 98;
  const resolvedYes = yes >= 98;
  const isLive      = !resolved && yes > 20 && yes < 80;

  if (resolved) {
    const c = resolvedYes ? '#34C07F' : '#F87171';
    return (
      <div style={{
        display: 'inline-flex', alignItems: 'center', gap: 7,
        padding: '6px 14px', borderRadius: 100,
        background: resolvedYes ? 'rgba(52,192,127,0.12)' : 'rgba(248,113,113,0.12)',
        border: `1px solid ${resolvedYes ? 'rgba(52,192,127,0.45)' : 'rgba(248,113,113,0.45)'}`,
      }}>
        <span style={{ width: 7, height: 7, borderRadius: '50%', background: c, display: 'inline-block', flexShrink: 0 }} />
        <span style={{ fontFamily: 'DM Mono,monospace', fontSize: 11, fontWeight: 700, color: c, letterSpacing: '0.3px' }}>
          RESOLVED — {resolvedYes ? 'YES' : 'NO'}
        </span>
      </div>
    );
  }

  if (isLive) {
    return (
      <div style={{
        display: 'inline-flex', alignItems: 'center', gap: 7,
        padding: '6px 14px', borderRadius: 100,
        background: 'rgba(52,192,127,0.07)', border: '1px solid rgba(52,192,127,0.2)',
      }}>
        <span style={{
          width: 7, height: 7, borderRadius: '50%', background: '#34C07F',
          display: 'inline-block', animation: 'blink 2s ease-in-out infinite',
          boxShadow: '0 0 6px rgba(52,192,127,0.7)', flexShrink: 0,
        }} />
        <span style={{ fontFamily: 'DM Mono,monospace', fontSize: 11, fontWeight: 600, color: '#34C07F', letterSpacing: '0.3px' }}>
          LIVE
        </span>
      </div>
    );
  }

  return (
    <div style={{
      display: 'inline-flex', alignItems: 'center', gap: 7,
      padding: '6px 14px', borderRadius: 100,
      background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(132,130,130,0.3)',
    }}>
      <span style={{ width: 7, height: 7, borderRadius: '50%', background: '#848282', display: 'inline-block', flexShrink: 0 }} />
      <span style={{ fontFamily: 'DM Mono,monospace', fontSize: 11, color: '#848282', letterSpacing: '0.3px' }}>OPEN</span>
    </div>
  );
}

// ─── STAT ROW ─────────────────────────────────────────────────────────────────
function StatRow({ label, val, valColor }) {
  return (
    <div className="m-stat-item">
      <span className="m-stat-label">{label}</span>
      <span className="m-stat-val" style={valColor ? { color: valColor } : {}}>{val}</span>
    </div>
  );
}

// ─── MAIN PAGE ────────────────────────────────────────────────────────────────
export default function MarketDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id     = params?.id;

  const [m, setM]                           = useState(null);
  const [loading, setLoading]               = useState(true);
  const [error, setError]                   = useState(null);
  const [tradeType, setTradeType]           = useState('buy');
  const [side, setSide]                     = useState('yes');
  const [amount, setAmount]                 = useState('');
  const [showTradeModal, setShowTradeModal] = useState(false);
  const [tradeSide, setTradeSide]           = useState('yes');
  const [priceHistory, setPriceHistory]     = useState([]);
  const [livePoints, setLivePoints]         = useState([]);
  const [priceInterval, setPriceInterval]   = useState('1w');
  const [chartLoading, setChartLoading]     = useState(false);
  const [liveMarket, setLiveMarket]         = useState(null);

  useRequireAuth();

  const isResolved    = m && (m.yes <= 2 || m.yes >= 98);
  const isLiveMarket  = m && !isResolved &&
    /\b(5 min|10 min|1 hour|today|tonight|this week|live)\b/i.test(m.q || '');

  // Fetch market metadata once on mount
  useEffect(() => {
    if (!id) return;
    setLoading(true);
    setError(null);
    getMarket(id)
      .then(md => {
        setM(md);
        if ((md.yes <= 2 || md.yes >= 98) && CRYPTO_CATS.has(md.cat)) {
          listMarkets()
            .then(all => setLiveMarket(all.find(mk => mk.id !== md.id && CRYPTO_CATS.has(mk.cat) && mk.yes > 2 && mk.yes < 98) || null))
            .catch(() => {});
        }
      })
      .catch(e => setError(e.message || 'Market not found'))
      .finally(() => setLoading(false));
  }, [id]);

  // market-p: Poll market metadata for live price updates every 15s
  useEffect(() => {
    if (!id || !isLiveMarket || isResolved) return;
    const pollId = setInterval(() => {
      getMarket(id)
        .then(md => {
          setM(prev => {
            if (!prev) return md;
            if (md.yes !== prev.yes) {
              setLivePoints(lp => [...lp, md.yes].slice(-50)); // Keep last 50 session points
            }
            return { ...prev, yes: md.yes, vol: md.vol };
          });
        })
        .catch(() => {});
    }, 5000); // market-p3: fast polling for session-live movement (5s)
    return () => clearInterval(pollId);
  }, [id, isLiveMarket, isResolved]);

  // Fetch price history when interval changes — retries up to 3x if backend is cold
  useEffect(() => {
    if (!id) return;
    let cancelled = false;

    const load = async (attempt = 1) => {
      setChartLoading(true);
      try {
        const prices = await getMarketPriceHistory(id, priceInterval);
        if (cancelled) return;
        if (prices.length < 2 && attempt < 3) {
          setTimeout(() => load(attempt + 1), 3000);
        } else {
          setPriceHistory(prices || []);
          setChartLoading(false);
        }
      } catch {
        if (!cancelled) {
          setPriceHistory([]);
          setChartLoading(false);
        }
      }
    };

    load();
    return () => { cancelled = true; };
  }, [id, priceInterval]);

  const payout = useMemo(() => {
    const amt  = parseFloat(amount) || 0;
    const prob = side === 'yes' ? (m?.yes || 50) : (100 - (m?.yes || 50));
    return (amt * (100 / Math.max(prob, 1))).toFixed(2);
  }, [amount, side, m]);

  const profit = useMemo(
    () => (parseFloat(payout) - (parseFloat(amount) || 0)).toFixed(2),
    [payout, amount]
  );


  const chartData = useMemo(() => { // market-p3: merge history with live session points for accuracy
    let combined = [];
    if (priceHistory && priceHistory.length > 1) {
      combined = [...priceHistory];
    }
    
    // Append session-live points
    if (livePoints.length > 0) {
      combined = [...combined, ...livePoints];
    } else if (isLiveMarket && m?.yes !== undefined && combined.length > 0) {
      // Ensure the very last point is always current if no livePoints yet
      combined = [...combined, m.yes];
    }
    
    return combined;
  }, [priceHistory, livePoints, isLiveMarket, m?.yes]);

  return (
    <AuthGate softGate>
      <div className="app">
        <div className="scroll">
          <div className="m-detail-layout">
            {loading ? (
              <div className="empty">
                <div className="empty-icon" style={{ animation: 'spin 1.2s linear infinite' }}>⟳</div>
                <div className="empty-text">Loading market…</div>
              </div>
            ) : error ? (
              <div className="empty">
                <div className="empty-icon">◇</div>
                <div className="empty-text">{error}</div>
                <button className="chip-btn" onClick={() => router.back()} style={{ marginTop: 12 }}>← Go back</button>
              </div>
            ) : !m ? (
              <div className="empty">
                <div className="empty-icon">◇</div>
                <div className="empty-text">Market not found</div>
              </div>
            ) : (
              <>
                <Header backHref="/signals" title="MARKET" />

                {/* Status + actions row */}
                <div style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  flexWrap: 'wrap', gap: 12, marginTop: 20, marginBottom: 20,
                }}>
                  <MarketStatusBadge yes={m.yes} />

                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    {isResolved && liveMarket && CRYPTO_CATS.has(m.cat) && (
                      <button className="mp-live-btn" onClick={() => router.push(`/market/${liveMarket.id}`)}>
                        Go to Live Market →
                      </button>
                    )}

                  </div>
                </div>

                {/* Market title */}
                <h1 style={{ fontSize: 'clamp(18px, 2.4vw, 26px)', fontWeight: 700, color: '#fff', margin: '0 0 20px', lineHeight: 1.3 }}>
                  {m.q}
                </h1>

                {/* Price */}
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 16, marginBottom: 24 }}>
                  <div style={{ fontFamily: 'Syne, sans-serif', fontSize: 52, fontWeight: 800, color: '#fff', lineHeight: 1 }}>
                    {m.yes ?? 50}¢
                  </div>
                  <div style={{ fontFamily: 'DM Mono,monospace', fontSize: 13, color: '#848282', letterSpacing: '0.3px' }}>
                    YES probability
                  </div>
                </div>

                {/* Interval tabs */}
                <div style={{ display: 'flex', gap: 6, marginBottom: 16 }}>
                  {INTERVALS.map(({ label, value }) => (
                    <button
                      key={value}
                      onClick={() => setPriceInterval(value)}
                      style={{
                        padding: '6px 14px', borderRadius: 100,
                        background: priceInterval === value ? 'rgba(52,192,127,0.12)' : '#111',
                        border: `1px solid ${priceInterval === value ? 'rgba(52,192,127,0.5)' : 'rgba(255,255,255,0.08)'}`,
                        color: priceInterval === value ? '#34C07F' : '#848282',
                        fontFamily: 'DM Mono,monospace', fontSize: 10, fontWeight: 600,
                        cursor: 'pointer', transition: 'all 0.18s',
                      }}
                    >
                      {label}
                    </button>
                  ))}
                </div>

                {/* Chart */}
                <div style={{
                  background: '#0a0a0a', border: '1px solid rgba(255,255,255,0.07)',
                  borderRadius: 20, padding: '24px 20px 16px', marginBottom: 28,
                  position: 'relative', overflow: 'hidden', minHeight: 280,
                }}>
                  {chartLoading && (
                    <div style={{
                      position: 'absolute', inset: 0, display: 'flex', alignItems: 'center',
                      justifyContent: 'center', background: 'rgba(10,10,10,0.75)',
                      zIndex: 10, borderRadius: 20,
                    }}>
                      <span style={{
                        fontFamily: 'DM Mono,monospace', fontSize: 11,
                        color: 'rgba(140,140,140,0.55)', animation: 'blink 1.4s ease-in-out infinite',
                      }}>
                        loading chart…
                      </span>
                    </div>
                  )}
                  <SVGLineChart data={chartData} isLive={!!isLiveMarket} />
                </div>

                {/* 2-col grid */}
                <div className="m-grid">

                  {/* LEFT: stats + rules + bot */}
                  <div className="m-left-col">
                    <div className="card-opaque" style={{ padding: 24, borderRadius: 20 }}>
                      <div className="m-title-small">Market Stats</div>
                      <div className="m-stat-list">
                        <StatRow label="Volume"   val={m.vol || '—'} />
                        <StatRow label="Category" val={m.cat || '—'} />
                        <StatRow label="YES"      val={`${m.yes ?? 50}¢`}         valColor="#34C07F" />
                        <StatRow label="NO"       val={`${100 - (m.yes ?? 50)}¢`} valColor="#F87171" />
                        <StatRow label="Status"   val={isResolved ? (m.yes >= 98 ? 'Resolved YES' : 'Resolved NO') : isLiveMarket ? 'Live' : 'Open'} />
                      </div>
                    </div>

                    <div className="m-rules-box">
                      <div className="m-rules-title">Rules</div>
                      <div className="m-rules-text">
                        This market resolves based on the stated outcome. Winning shares pay $1.00 each.
                        Losing shares pay $0.00. Markets auto-settle when Polymarket resolves.
                      </div>
                    </div>

                    <button
                      onClick={() => window.dispatchEvent(new Event('open-nortbot'))}
                      style={{
                        marginTop: 24,
                        display: 'inline-flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        padding: '9px 20px',
                        borderRadius: 100,
                        background: 'linear-gradient(90deg, #34C07F 0%, #0066FF 100%)',
                        color: '#fff',
                        fontFamily: 'DM Mono, monospace',
                        fontWeight: 700,
                        fontSize: 11,
                        letterSpacing: '0.4px',
                        cursor: 'pointer',
                        border: 'none',
                        boxShadow: '0 4px 20px rgba(52,192,127,0.25)',
                      }}
                    >
                      ASK NORT BOT
                    </button>
                  </div>

                  {/* RIGHT: trade panel */}
                  <div className="m-right-col">
                    <div className="card-opaque" style={{ padding: 24, borderRadius: 20 }}>
                      <div className="m-trade-tabs">
                        <button className={`m-trade-tab ${tradeType === 'buy'  ? 'on' : ''}`} onClick={() => setTradeType('buy')}>Buy</button>
                        <button className={`m-trade-tab ${tradeType === 'sell' ? 'on' : ''}`} onClick={() => setTradeType('sell')}>Sell</button>
                      </div>

                      <div className="modal-sides" style={{ marginBottom: 20 }}>
                        <button className={`side-btn ${side === 'yes' ? 'active-yes' : ''}`} onClick={() => setSide('yes')}>
                          <span className="side-label">▲ YES</span>
                          <span className="side-price">{m.yes ?? 50}¢</span>
                        </button>
                        <button className={`side-btn ${side === 'no' ? 'active-no' : ''}`} onClick={() => setSide('no')}>
                          <span className="side-label">▼ NO</span>
                          <span className="side-price">{100 - (m.yes ?? 50)}¢</span>
                        </button>
                      </div>

                      <div className="modal-input-label">Amount (paper USDC)</div>
                      <div className="modal-input-wrap">
                        <span className="modal-input-prefix">$</span>
                        <input
                          type="number"
                          className="modal-input"
                          placeholder="0.00"
                          value={amount}
                          min="1"
                          inputMode="decimal"
                          onChange={e => setAmount(e.target.value)}
                        />
                      </div>

                      <div className="modal-payout">
                        <div>
                          <div className="payout-label">Potential Payout</div>
                          <div className="payout-val">{amount ? `$${payout}` : '—'}</div>
                        </div>
                        <div style={{ textAlign: 'right' }}>
                          <div className="payout-label">Profit</div>
                          <div className="payout-val" style={{ color: '#34C07F' }}>{amount ? `+$${profit}` : '—'}</div>
                        </div>
                      </div>

                      <button
                        className="modal-cta"
                        onClick={() => { if (!m) return; setTradeSide(side); setShowTradeModal(true); }}
                        disabled={!!isResolved}
                        style={isResolved ? { opacity: 0.35, cursor: 'not-allowed' } : {}}
                      >
                        {isResolved ? 'Market Resolved' : 'Confirm Trade'}
                      </button>

                      {isResolved && (
                        <div style={{ textAlign: 'center', marginTop: 10, fontFamily: 'DM Mono,monospace', fontSize: 11, color: 'rgba(140,140,140,0.55)' }}>
                          This market has resolved — no new trades accepted
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
        <Navbar active="markets" />
      </div>

      {showTradeModal && m && (
        <TradeModal
          signal={{ id: m.id, q: m.q, yes: m.yes, cat: m.cat, vol: m.vol }}
          initialSide={tradeSide}
          onClose={() => setShowTradeModal(false)}
          onSuccess={() => setShowTradeModal(false)}
        />
      )}

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </AuthGate>
  );
}
