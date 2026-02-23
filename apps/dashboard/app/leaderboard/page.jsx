'use client';
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
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
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
              {p.isMe && <span style={{ fontSize: 9, color: 'var(--g3)' }}> (you)</span>}
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

  return (
    <AuthGate>
      <div className="app">
        <div className="header">
          <div className="header-logo">Leaderboard</div>
          <div className="header-right">
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
              <div style={{ textAlign: 'center', color: 'var(--g3)' }}>Loading...</div>
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
          )}
        </div>

        <Navbar active="leaderboard" />
      </div>
    </AuthGate>
  );
}
