'use client';
import React, { useState, useEffect } from 'react';
import AuthGate from '@/components/AuthGate';
import Navbar from '@/components/Navbar';
import Header from '@/components/Header';
import { getLeaderboard, getMyRank } from '@/lib/api';
import { useAuth } from '@/hooks/useAuth';
import { useTradingMode } from '@/components/TradingModeContext';

const RANK_COLORS = ['#f59e0b', '#a0a0a0', '#b45309'];

function PodiumCard({ entry, pos }) {
  return (
    <div className="podium-slot" style={{ order: pos === 0 ? 1 : pos === 1 ? 0 : 2 }}>
      <div className="podium-name">{entry.badge.emoji} {entry.display_name}</div>
      <div className="podium-pnl" style={{ color: entry.net_pnl >= 0 ? '#34C07F' : '#F87171' }}>
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
  if (!streak) return <span style={{ color: '#848282', fontFamily: 'DM Mono, monospace', fontSize: 11 }}>--</span>;
  return <span style={{ fontFamily: 'DM Mono, monospace', fontSize: 11, color: '#f59e0b' }}>🔥 x{streak}</span>;
}

function ModeTab({ label, active, color, onClick }) {
  return (
    <button
      onClick={onClick}
      style={{
        padding:       '6px 16px',
        borderRadius:  20,
        border:        `1.5px solid ${active ? color : '#848282'}`,
        background:    active ? color + '18' : 'transparent',
        color:         active ? color : '#848282',
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

  const [tab, setTab]         = useState(tradingMode || 'paper');
  const [board, setBoard]     = useState([]);
  const [myRank, setMyRank]   = useState(null);
  const [loading, setLoading] = useState(true);

  // Fetch leaderboard + my rank whenever tab changes
  useEffect(() => {
    setLoading(true);
    getLeaderboard(50, tab)
      .then(setBoard)
      .catch(() => setBoard([]))
      .finally(() => setLoading(false));
  }, [tab]);

  useEffect(() => {
    if (!walletAddress) return;
    getMyRank(walletAddress, tab)
      .then(setMyRank)
      .catch(() => setMyRank(null));
  }, [walletAddress, tab]);

  const isReal     = tab === 'real';
  const showPodium = board.length >= 2;
  const top3       = board.slice(0, Math.min(3, board.length));

  const portfolioLabel = isReal ? 'USDC' : 'Portfolio';

  return (
    <AuthGate softGate>
      <div className={`app${isReal ? ' real-mode' : ''}`}>
        <Header title="RANKS" hideLogo={true} />

        <div className="app-scroll">
          <div className="page-header" style={{ marginBottom: '32px' }}>
            <div>
              <div className="page-title" style={{ fontFamily: 'Syne', fontWeight: 800, fontSize: '32px', letterSpacing: '-1px' }}>
                {isReal ? 'REAL RANKS' : 'PAPER RANKS'}
              </div>
              <div className="page-meta">
                {board.length} traders — ranked by {isReal ? 'real USDC balance' : 'portfolio value'}
              </div>
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <ModeTab
                label="◈ Paper"
                active={tab === 'paper'}
                color="#34C07F"
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

          {myRank && (
            <div className="card-opaque fu d1" style={{ 
              borderRadius: '20px',
              padding: '24px',
              marginBottom: '32px',
              borderColor: isReal ? '#F59E0B' : undefined 
            }}>
              <div className="my-rank-left">
                <div className="my-rank-num" style={{ fontSize: '32px', fontWeight: 800, fontFamily: 'Syne' }}>#{myRank.rank}</div>
                <div>
                  <div className="my-rank-name" style={{ fontSize: '18px', fontWeight: 600 }}>You · {myRank.display_name}</div>
                  <BadgePill badge={myRank.badge} />
                </div>
              </div>
              <div className="my-rank-stats">
                <div className="my-stat">
                  <div className="my-stat-val" style={{ color: myRank.net_pnl >= 0 ? '#34C07F' : '#F87171' }}>
                    {myRank.net_pnl >= 0 ? '+' : ''}${myRank.net_pnl.toFixed(2)}
                  </div>
                  <div className="my-stat-label">P&L</div>
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
              <div className="xp-bar-wrap" style={{ marginTop: '20px' }}>
                <div className="xp-bar-track" style={{ background: 'rgba(255,255,255,0.05)', height: '6px', borderRadius: '100px' }}>
                  <div className="xp-bar-fill" style={{ 
                    background: '#34C07F', 
                    width: Math.min(100, (myRank.xp % 500) / 5) + '%',
                    height: '100%',
                    borderRadius: '100px'
                  }} />
                </div>
                <span className="xp-label" style={{ fontSize: '10px', color: '#848282', marginTop: '6px', display: 'block' }}>{myRank.xp % 500}/500 XP to next rank</span>
              </div>
            </div>
          )}

          {showPodium && (
            <div className="podium-wrap fu d2" style={{ marginBottom: '40px' }}>
              {top3.map((entry, i) => (
                <PodiumCard key={entry.telegram_user_id} entry={entry} pos={i} />
              ))}
            </div>
          )}

          <div className="card-opaque fu d3" style={{ borderRadius: '20px', overflow: 'hidden' }}>
            <div className="lb-table-header" style={{ padding: '16px 20px', background: 'rgba(255,255,255,0.03)', borderBottom: '1px solid rgba(255, 255, 255, 0.08)' }}>
              <span>#</span>
              <span>Trader</span>
              <span className="lb-hide-sm">Trades</span>
              <span className="lb-hide-sm">Win Rate</span>
              <span className="lb-hide-sm">Streak</span>
              <span>P&L</span>
              <span>{portfolioLabel}</span>
            </div>
            {loading ? (
              [1,2,3,4,5].map(i => (
                <div key={i} className="lb-row" style={{ padding: '16px 20px', borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                  <div className="skel-line w100" style={{ height: 14, borderRadius: 6 }} />
                </div>
              ))
            ) : board.length === 0 ? (
              <div className="empty" style={{ padding: '40px 20px' }}>
                <div className="empty-icon">◇</div>
                <div className="empty-text">No traders yet</div>
              </div>
            ) : (
              board.map(entry => (
                <div
                  key={entry.telegram_user_id}
                  className={'lb-row' + (myRank?.telegram_user_id === entry.telegram_user_id ? ' lb-row-me' : '')}
                  style={{
                    padding: '16px 20px',
                    borderBottom: '1px solid rgba(255, 255, 255, 0.04)',
                    background: myRank?.telegram_user_id === entry.telegram_user_id ? 'radial-gradient(circle at 0% 0%, rgba(52, 192, 127, 1) 0%, rgba(0, 102, 255, 0.95) 25%, transparent 75%)' : 'transparent'
                  }}
                >
                  <span className="lb-rank" style={{ fontWeight: 700 }}>{entry.rank}</span>
                  <span className="lb-trader">
                    <BadgePill badge={entry.badge} />
                    <span className="lb-name" style={{ marginLeft: '8px' }}>{entry.display_name}</span>
                  </span>
                  <span className="lb-hide-sm lb-mono" style={{ opacity: 0.6 }}>{entry.total_trades}</span>
                  <span className="lb-hide-sm lb-mono" style={{ opacity: 0.6 }}>{entry.win_rate}%</span>
                  <span className="lb-hide-sm"><StreakFlame streak={entry.streak} /></span>
                  <span className="lb-mono" style={{ color: entry.net_pnl >= 0 ? '#34C07F' : '#F87171' }}>
                    {entry.net_pnl >= 0 ? '+' : ''}${entry.net_pnl.toFixed(0)}
                  </span>
                  <span className="lb-mono">
                    ${(isReal ? 0 : entry.portfolio_value ?? 0).toFixed(isReal ? 2 : 0)}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>

        <Navbar active="leaderboard" />
      </div>
    </AuthGate>
  );
}
