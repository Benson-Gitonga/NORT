'use client';
import React, { useState, useEffect } from 'react';
import AuthGate from '@/components/AuthGate';
import Navbar from '@/components/Navbar';
import { getLeaderboard, getMyRank } from '@/lib/api';
import { useAuth } from '@/hooks/useAuth';

const RANK_COLORS = ['#f59e0b', '#a0a0a0', '#b45309'];
const RANK_LABELS = ['gold', 'silver', 'bronze'];

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
  return <span style={{ fontFamily: 'DM Mono, monospace', fontSize: 11, color: '#f59e0b' }}>x{streak}</span>;
}

export default function LeaderboardPage() {
  const { walletAddress } = useAuth();
  const [board, setBoard] = useState([]);
  const [myRank, setMyRank] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      getLeaderboard(50),
      walletAddress ? getMyRank(walletAddress) : Promise.resolve(null),
    ]).then(([lb, me]) => {
      setBoard(lb);
      setMyRank(me);
    }).finally(() => setLoading(false));
  }, [walletAddress]);

  const top3 = board.slice(0, 3);
  const rest  = board.slice(3);

  return (
    <AuthGate>
      <div className="app">
        <div className="header">
          <div className="header-logo">Leaderboard</div>
          <div className="header-right">
            <div className="live-pill"><span className="live-dot" />Live</div>
          </div>
        </div>

        <div className="app-scroll">
          <div className="page-header">
            <div>
              <div className="page-title">Paper Trading Ranks</div>
              <div className="page-meta">{board.length} traders - ranked by portfolio value</div>
            </div>
          </div>

          {myRank && (
            <div className="my-rank-card fu d1">
              <div className="my-rank-left">
                <div className="my-rank-num">#{myRank.rank}</div>
                <div>
                  <div className="my-rank-name">You</div>
                  <BadgePill badge={myRank.badge} />
                </div>
              </div>
              <div className="my-rank-stats">
                <div className="my-stat">
                  <div className="my-stat-val" style={{ color: myRank.net_pnl >= 0 ? 'var(--green)' : 'var(--red)' }}>
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
              <div className="xp-bar-wrap">
                <div className="xp-bar-track">
                  <div className="xp-bar-fill" style={{ width: Math.min(100, (myRank.xp % 500) / 5) + '%' }} />
                </div>
                <span className="xp-label">{myRank.xp % 500}/500 XP to next rank</span>
              </div>
            </div>
          )}

          {!loading && top3.length === 3 && (
            <div className="podium-wrap fu d2">
              {top3.map((entry, i) => (
                <PodiumCard key={entry.telegram_user_id} entry={entry} pos={i} />
              ))}
            </div>
          )}

          <div className="lb-table fu d3">
            <div className="lb-table-header">
              <span>#</span>
              <span>Trader</span>
              <span className="lb-hide-sm">Trades</span>
              <span className="lb-hide-sm">Win Rate</span>
              <span className="lb-hide-sm">Streak</span>
              <span>P&L</span>
              <span>Portfolio</span>
            </div>

            {loading
              ? [1, 2, 3, 4, 5].map(i => (
                  <div key={i} className="lb-row skeleton-row">
                    <div className="skel-line w40" style={{ height: 10, borderRadius: 4 }} />
                    <div className="skel-line w70" style={{ height: 10, borderRadius: 4 }} />
                    <div className="skel-line w40" style={{ height: 10, borderRadius: 4 }} />
                  </div>
                ))
              : rest.map(entry => (
                  <div key={entry.telegram_user_id} className={'lb-row' + (myRank && myRank.telegram_user_id === entry.telegram_user_id ? ' lb-row-me' : '')}>
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
                    <span className="lb-mono">${entry.portfolio_value.toFixed(0)}</span>
                  </div>
                ))
            }
          </div>

          {!loading && board.length === 0 && (
            <div className="empty">
              <div className="empty-icon">trophy</div>
              <div className="empty-text">No traders yet. Be the first!</div>
            </div>
          )}
        </div>

        <Navbar active="leaderboard" />
      </div>
    </AuthGate>
  );
}
