'use client';
<<<<<<< HEAD
import React, { useState, useEffect } from 'react';
import AuthGate from '@/components/AuthGate';
import Navbar from '@/components/Navbar';
import { getLeaderboard, getMyRank } from '@/lib/api';
import { useAuth } from '@/hooks/useAuth';

const RANK_COLORS = ['#f59e0b', '#a0a0a0', '#b45309'];
const RANK_LABELS = ['🥇', '🥈', '🥉'];

function PodiumCard({ entry, pos }) {
  const heights = ['h-36', 'h-24', 'h-20'];
  const sizes   = ['text-3xl', 'text-2xl', 'text-xl'];
  return (
    <div className="podium-slot" style={{ order: pos === 0 ? 1 : pos === 1 ? 0 : 2 }}>
      <div className="podium-name">{entry.badge.emoji} {entry.display_name}</div>
      <div className="podium-pnl" style={{ color: entry.net_pnl >= 0 ? 'var(--green)' : 'var(--red)' }}>
        {entry.net_pnl >= 0 ? '+' : ''}{entry.net_pnl_pct.toFixed(1)}%
      </div>
      <div className="podium-bar" style={{ height: pos === 0 ? 120 : pos === 1 ? 80 : 60, background: RANK_COLORS[pos] }}>
        <span className="podium-rank">{RANK_LABELS[pos]}</span>
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
  if (!streak) return <span style={{ color: 'var(--g3)', fontFamily: 'DM Mono, monospace', fontSize: 11 }}>—</span>;
  return <span style={{ fontFamily: 'DM Mono, monospace', fontSize: 11, color: '#f59e0b' }}>🔥 {streak}</span>;
}

export default function LeaderboardPage() {
  const { walletAddress } = useAuth();
  const [board, setBoard]     = useState([]);
  const [myRank, setMyRank]   = useState(null);
=======
import React, { useEffect, useState } from 'react';
import { getLeaderboard } from '@/lib/api';
import Navbar from '@/components/Navbar';
import AuthGate from '@/components/AuthGate';

const LB_TYPES = [
  { key: 'pts', label: 'Points' },
  { key: 'pnl', label: 'P&L' },
  { key: 'wr', label: 'Win%' },
  { key: 'act', label: 'Active' },
  { key: 'str', label: 'Streak' },
];

export default function LeaderboardPage() {
  const [data, setData] = useState([]);
  const [type, setType] = useState('pts');
>>>>>>> cb9d82afafe3ae19e7383359b11d2847e14f3853
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
<<<<<<< HEAD
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
=======
    getLeaderboard(type).then(d => {
      setData(d);
      setLoading(false);
    });
  }, [type]);

  const top3 = data.slice(0, 3);
  const rest = data.slice(3);
  const me = data.find(d => d.isMe);
  const rankMap = { pts: '#5', pnl: '#4', wr: '#4', act: '#5', str: '#4' };

  const renderPodium = () => {
    const order = [top3[1], top3[0], top3[2]];
    const classes = ['p2', 'p1', 'p3'];
    const bars = ['b2', 'b1', 'b3'];
    const ranks = ['#2', '#1', '#3'];

    return order.map((p, i) => {
      if (!p) return null;
      return (
        <div key={i} className="pod-item">
          <div className={`pod-av ${classes[i]}`}>
            {i === 1 && <span className="pod-crown">👑</span>}
            {p.av}
          </div>
          <div className="pod-name">@{p.name.slice(0, 8)}</div>
          <div className="pod-val">{p.score}</div>
          <div className={`pod-bar ${bars[i]}`} />
          <div className="pod-rnk">{ranks[i]}</div>
        </div>
      );
    });
  };

  const renderList = () => {
    return rest.map((p, i) => {
      const rank = i + 4;
      const sc = p.sc || '';
      return (
        <div key={p.id} className={`lb-row ${p.isMe ? 'me' : ''}`}>
          <div className={`lb-rank ${rank <= 3 ? 'top' : ''}`}>{rank}</div>
          <div className={`lb-av ${p.isMe ? 'mav' : ''}`}>{p.av}</div>
          <div className="lb-info">
            <div className="lb-name">
              @{p.name}
              {p.isMe && <span style={{ fontSize: 9, color: 'var(--text-muted)' }}> (you)</span>}
            </div>
            <div className="lb-meta">{p.meta}</div>
            {p.badges && p.badges.length > 0 && (
              <div className="lb-bdgs">
                {p.badges.map((b, idx) => (
                  <span key={idx}>{b}</span>
                ))}
              </div>
            )}
          </div>
          <div className={`lb-score ${sc}`}>{p.score}</div>
        </div>
      );
    });
  };
>>>>>>> cb9d82afafe3ae19e7383359b11d2847e14f3853

  return (
    <AuthGate>
      <div className="app">
        <div className="header">
          <div className="header-logo">Leaderboard</div>
          <div className="header-right">
<<<<<<< HEAD
            <div className="live-pill"><span className="live-dot" />Live</div>
          </div>
        </div>

        <div className="app-scroll">
          <div className="page-header">
            <div>
              <div className="page-title">Paper Trading Ranks</div>
              <div className="page-meta">{board.length} traders · ranked by portfolio value</div>
            </div>
          </div>

          {/* MY RANK CARD */}
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
              {/* XP progress bar */}
              <div className="xp-bar-wrap">
                <div className="xp-bar-track">
                  <div className="xp-bar-fill" style={{ width: `${Math.min(100, (myRank.xp % 500) / 5)}%` }} />
                </div>
                <span className="xp-label">{myRank.xp % 500}/500 XP to next rank</span>
              </div>
            </div>
          )}

          {/* PODIUM */}
          {!loading && top3.length === 3 && (
            <div className="podium-wrap fu d2">
              {top3.map((entry, i) => (
                <PodiumCard key={entry.telegram_user_id} entry={entry} pos={i} />
              ))}
            </div>
          )}

          {/* REST OF TABLE */}
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
              ? [1,2,3,4,5].map(i => (
                  <div key={i} className="lb-row skeleton-row">
                    <div className="skel-line w40" style={{ height: 10, borderRadius: 4 }} />
                    <div className="skel-line w70" style={{ height: 10, borderRadius: 4 }} />
                    <div className="skel-line w40" style={{ height: 10, borderRadius: 4 }} />
                  </div>
                ))
              : rest.map(entry => (
                  <div key={entry.telegram_user_id} className={`lb-row ${myRank?.telegram_user_id === entry.telegram_user_id ? 'lb-row-me' : ''}`}>
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
              <div className="empty-icon">🏆</div>
              <div className="empty-text">No traders yet. Be the first!</div>
            </div>
=======
            <div className="live-pill">
              <span className="live-dot" />
              Live
            </div>
          </div>
        </div>

        <div className="scroll">
          <div className="lb-type-tabs fu d1">
            {LB_TYPES.map(t => (
              <button
                key={t.key}
                className={`lb-tab ${type === t.key ? 'on' : ''}`}
                onClick={() => setType(t.key)}
              >
                {t.label}
              </button>
            ))}
          </div>

          {loading ? (
            <div className="podium fu d2">
              <div style={{ textAlign: 'center', color: 'var(--text-muted)' }}>Loading...</div>
            </div>
          ) : (
            <>
              <div className="podium fu d2">{renderPodium()}</div>

              {me && (
                <div className="my-rank-bar fu d3">
                  <div className="mrb-l">Your rank &middot; @{me.name}</div>
                  <div className="mrb-r">{rankMap[type]} &middot; {me.score}</div>
                </div>
              )}

              <div className="lb-list fu d4">{renderList()}</div>
            </>
>>>>>>> cb9d82afafe3ae19e7383359b11d2847e14f3853
          )}
        </div>

        <Navbar active="leaderboard" />
      </div>
    </AuthGate>
  );
}
