'use client';
import React, { useState, useEffect } from 'react';
import AuthGate from '@/components/AuthGate';
import Navbar from '@/components/Navbar';
import { getLeaderboard, getMyRank } from '@/lib/api';
import { useAuth } from '@/hooks/useAuth';
import { useTradingMode } from '@/components/TradingModeContext';

const RANK_COLORS = ['#f59e0b', '#a0a0a0', '#b45309'];

function PodiumCard({ entry, pos }) {
  return (
    <div className="podium-slot" style={{ order: pos === 0 ? 1 : pos === 1 ? 0 : 2 }}>
      <div className="podium-name">{entry.badge.emoji} {entry.display_name}</div>
      <div className="podium-pnl" style={{ color: entry.net_pnl >= 0 ? 'var(--green)' : 'var(--red)' }}>
        {entry.net_pnl >= 0 ? '+' : ''}{entry.net_pnl_pct.toFixed(1)}%
      </div>
      <div className="podium-bar" style={{ height: pos === 0 ? 120 : pos === 1 ? 80 : 60, background: RANK_COLORS[pos] }}>
        <span className="podium-rank">{pos + 1}</span>
      </div>
      <div className="podium-xp">{entry.xp} XP</div>
    </div>
  );
}

function BadgePill({ badge }) {
  return (
    <span className="badge-pill" style={{ background: badge.color + '18', color: badge.color, borderColor: badge.color + '40' }}>
      {badge.emoji} {badge.label}
    </span>
  );
}

function StreakFlame({ streak }) {
  if (!streak) return <span style={{ color: 'var(--g3)', fontFamily: 'DM Mono, monospace', fontSize: 11 }}>--</span>;
  return <span style={{ fontFamily: 'DM Mono, monospace', fontSize: 11, color: '#f59e0b' }}>🔥 x{streak}</span>;
}

// ── Mode toggle pill ──────────────────────────────────────────────────────────
function ModeTab({ label, active, color, onClick }) {
  return (
    <button
      onClick={onClick}
      style={{
        padding:       '6px 16px',
        borderRadius:  20,
        border:        `1.5px solid ${active ? color : 'var(--border)'}`,
        background:    active ? color + '18' : 'transparent',
        color:         active ? color : 'var(--muted)',
        fontSize:      12,
        fontFamily:    'DM Mono, monospace',
        fontWeight:    active ? 700 : 400,
        cursor:        'pointer',
        letterSpacing: '0.03em',
        transition:    'all 0.15s',
      }}
    >
      {label}
    </button>
  );
}

export default function LeaderboardPage() {
  const { walletAddress } = useAuth();
  const { mode: tradingMode } = useTradingMode();

  // Default tab = user's current trading mode
  const [tab, setTab]         = useState(tradingMode || 'paper');
  const [board, setBoard]     = useState([]);
  const [myRank, setMyRank]   = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState(null);

  // When user's trading mode changes, switch the default tab
  useEffect(() => {
    setTab(tradingMode || 'paper');
  }, [tradingMode]);

  useEffect(() => {
    setLoading(true);
    setError(null);
    setBoard([]);
    setMyRank(null);
    Promise.all([
      getLeaderboard(50, tab),
      walletAddress ? getMyRank(walletAddress, tab) : Promise.resolve(null),
    ])
      .then(([lb, me]) => { setBoard(lb); setMyRank(me); })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [walletAddress, tab]);

  const isReal     = tab === 'real';
  const showPodium = board.length >= 2;
  const top3       = board.slice(0, Math.min(3, board.length));

  // Label the balance column correctly per mode
  const portfolioLabel = isReal ? 'USDC' : 'Portfolio';

  return (
    <AuthGate>
      <div className={`app${isReal ? ' real-mode' : ''}`}>
        <div className="header">
          <div className="header-logo">Leaderboard</div>
          <div className="header-right">
            <div className="live-pill"><span className="live-dot" />Live</div>
          </div>
        </div>

        <div className="app-scroll">
          {/* ── Page header + mode toggle ── */}
          <div className="page-header">
            <div>
              <div className="page-title">
                {isReal ? '⚡ Real Trading Ranks' : '◈ Paper Trading Ranks'}
              </div>
              <div className="page-meta">
                {loading ? 'Loading...' : `${board.length} trader${board.length !== 1 ? 's' : ''} — ranked by ${isReal ? 'real USDC balance' : 'portfolio value'}`}
              </div>
            </div>
            {/* Mode tab toggle */}
            <div style={{ display: 'flex', gap: 8 }}>
              <ModeTab
                label="◈ Paper"
                active={tab === 'paper'}
                color="var(--teal)"
                onClick={() => setTab('paper')}
              />
              <ModeTab
                label="⚡ Real"
                active={tab === 'real'}
                color="#F59E0B"
                onClick={() => setTab('real')}
              />
            </div>
          </div>

          {/* ── My Rank card ── */}
          {myRank ? (
            <div className="my-rank-card fu d1" style={{ borderColor: isReal ? 'rgba(245,158,11,0.3)' : undefined }}>
              <div className="my-rank-left">
                <div className="my-rank-num">#{myRank.rank}</div>
                <div>
                  <div className="my-rank-name">You · {myRank.display_name}</div>
                  <BadgePill badge={myRank.badge} />
                </div>
              </div>
              <div className="my-rank-stats">
                <div className="my-stat">
                  <div className="my-stat-val" style={{ color: myRank.net_pnl >= 0 ? 'var(--green)' : 'var(--red)' }}>
                    {myRank.net_pnl >= 0 ? '+' : ''}${myRank.net_pnl.toFixed(2)}
                  </div>
                  <div className="my-stat-label">P&amp;L</div>
                </div>
                <div className="my-stat">
                  <div className="my-stat-val">{myRank.win_rate}%</div>
                  <div className="my-stat-label">Win Rate</div>
                </div>
                <div className="my-stat">
                  <div className="my-stat-val">{myRank.xp}</div>
                  <div className="my-stat-label">XP</div>
                </div>
                <div className="my-stat">
                  <StreakFlame streak={myRank.streak} />
                  <div className="my-stat-label">Streak</div>
                </div>
              </div>
              <div className="xp-bar-wrap">
                <div className="xp-bar-track">
                  <div className="xp-bar-fill" style={{ width: Math.min(100, (myRank.xp % 500) / 5) + '%' }} />
                </div>
                <span className="xp-label">{myRank.xp % 500}/500 XP to next rank</span>
              </div>
            </div>
          ) : !loading && walletAddress && (
            <div className="my-rank-card fu d1" style={{ textAlign: 'center', padding: 20 }}>
              <div style={{ fontSize: 28, marginBottom: 8 }}>{isReal ? '⚡' : '🏆'}</div>
              <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 4 }}>You're not ranked yet</div>
              <div style={{ fontSize: 12, color: 'var(--g3)' }}>
                {isReal
                  ? 'Place your first real trade to appear on the board'
                  : 'Place your first paper trade to appear on the board'}
              </div>
            </div>
          )}

          {/* ── Real mode notice ── */}
          {isReal && !loading && board.length === 0 && (
            <div className="empty fu d2">
              <div className="empty-icon">⚡</div>
              <div className="empty-text">No real trades yet — be the first real trader!</div>
            </div>
          )}

          {error ? (
            <div className="empty fu d2">
              <div className="empty-icon">!</div>
              <div className="empty-text">Failed to load: {error}</div>
            </div>
          ) : loading ? (
            <div className="lb-table fu d3">
              {[1,2,3,4,5].map(i => (
                <div key={i} className="lb-row skeleton-row">
                  <div className="skel-line w40" style={{ height: 10, borderRadius: 4 }} />
                  <div className="skel-line w70" style={{ height: 10, borderRadius: 4 }} />
                  <div className="skel-line w40" style={{ height: 10, borderRadius: 4 }} />
                </div>
              ))}
            </div>
          ) : board.length === 0 ? null : (
            <>
              {/* ── Podium ── */}
              {showPodium && (
                <div className="podium-wrap fu d2">
                  {top3.map((entry, i) => (
                    <PodiumCard key={entry.telegram_user_id} entry={entry} pos={i} />
                  ))}
                </div>
              )}

              {/* ── Full table ── */}
              <div className="lb-table fu d3">
                <div className="lb-table-header">
                  <span>#</span>
                  <span>Trader</span>
                  <span className="lb-hide-sm">Trades</span>
                  <span className="lb-hide-sm">Win Rate</span>
                  <span className="lb-hide-sm">Streak</span>
                  <span>P&amp;L</span>
                  <span>{portfolioLabel}</span>
                </div>
                {board.map(entry => (
                  <div
                    key={entry.telegram_user_id}
                    className={'lb-row' + (myRank?.telegram_user_id === entry.telegram_user_id ? ' lb-row-me' : '')}
                    style={isReal ? { borderLeft: '2px solid rgba(245,158,11,0.2)' } : undefined}
                  >
                    <span className="lb-rank">{entry.rank}</span>
                    <span className="lb-trader">
                      <BadgePill badge={entry.badge} />
                      <span className="lb-name">{entry.display_name}</span>
                    </span>
                    <span className="lb-hide-sm lb-mono">{entry.total_trades}</span>
                    <span className="lb-hide-sm lb-mono">{entry.win_rate}%</span>
                    <span className="lb-hide-sm"><StreakFlame streak={entry.streak} /></span>
                    <span className="lb-mono" style={{ color: entry.net_pnl >= 0 ? 'var(--green)' : 'var(--red)' }}>
                      {entry.net_pnl >= 0 ? '+' : ''}${entry.net_pnl.toFixed(0)}
                    </span>
                    <span className="lb-mono">
                      ${(isReal ? entry.real_balance_usdc : entry.portfolio_value ?? 0).toFixed(isReal ? 2 : 0)}
                    </span>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>

        <Navbar active="leaderboard" />
      </div>
    </AuthGate>
  );
}
