'use client';
import React, { useEffect, useState } from 'react';
import { getAchievements, getUserStats } from '@/lib/api';
import Navbar from '@/components/Navbar';
import AuthGate from '@/components/AuthGate';

export default function AchievementsPage() {
  const [achievements, setAchievements] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [popup, setPopup] = useState(null);

  useEffect(() => {
    Promise.all([getAchievements(), getUserStats()])
      .then(([ach, st]) => {
        setAchievements(ach);
        setStats(st);
      })
      .finally(() => setLoading(false));
  }, []);

  const earned = achievements.filter(a => a.earned);
  const locked = achievements.filter(a => !a.earned);
  const totalXP = earned.reduce((sum, a) => sum + a.xp, 0);

  const handleUnlock = (a) => {
    if (a.earned) setPopup(a);
  };

  useEffect(() => {
    if (popup) {
      const timer = setTimeout(() => setPopup(null), 3200);
      return () => clearTimeout(timer);
    }
  }, [popup]);

  return (
    <AuthGate>
      <div className="app">
        <div className="header">
          <div className="header-logo">Badges</div>
          <div className="header-right">
            <div className="live-pill">
              <span className="live-dot" />
              {earned.length} / {achievements.length}
            </div>
          </div>
        </div>

        <div className="scroll">
          {loading ? (
            <div style={{ padding: 20, textAlign: 'center', color: 'var(--g3)' }}>Loading...</div>
          ) : (
            <>
              <div className="xp-card fu d1">
                <div className="xp-ring">
                  <svg viewBox="0 0 54 54">
                    <circle className="xp-bg" cx="27" cy="27" r="22" />
                    <circle
                      className="xp-fg"
                      cx="27"
                      cy="27"
                      r="22"
                      style={{
                        strokeDasharray: 138,
                        strokeDashoffset: 138 - (138 * (stats?.xpProgress || 0)) / 100,
                      }}
                    />
                  </svg>
                  <div className="xp-ctr">{stats?.xpProgress || 0}%</div>
                </div>
                <div className="xp-info">
                  <div className="xp-lbl">Total XP</div>
                  <div className="xp-val">{stats?.xp?.toLocaleString() || 0}</div>
                  <div className="xp-sub">
                    {stats?.xpToNextLevel || 0} XP to next level &middot; Rank #{stats?.rank || '—'}
                  </div>
                </div>
                <div className="str-pill">🔥 {stats?.streak || 0}</div>
              </div>

              <div className="sec-lbl fu d2">
                <span className="sec-t">Earned &middot; {earned.length}</span>
                <span className="sec-t">+{totalXP.toLocaleString()} XP</span>
              </div>

              <div className="ach-grid fu d3">
                {earned.map(a => (
                  <div key={a.id} className="ach-card earned" onClick={() => handleUnlock(a)}>
                    <div className="ach-icon">{a.icon}</div>
                    <div className="ach-name">{a.name}</div>
                    <div className="ach-desc">{a.desc}</div>
                    <div className="ach-xp ex">
                      +{a.xp} XP
                      {a.isNew && <span className="new-tag">NEW</span>}
                    </div>
                  </div>
                ))}
              </div>

              <div className="sec-lbl fu d4" style={{ marginTop: 6 }}>
                <span className="sec-t">Locked &middot; {locked.length}</span>
                <span className="sec-t">Keep trading</span>
              </div>

              <div className="ach-grid fu d5">
                {locked.map(a => (
                  <div key={a.id} className="ach-card locked">
                    <div className="ach-icon">{a.icon}</div>
                    <div className="ach-name">{a.name}</div>
                    <div className="ach-desc">{a.desc}</div>
                    <div className="ach-xp">+{a.xp} XP</div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>

        {popup && (
          <div className="ach-popup">
            <div className="apu-icon">{popup.icon}</div>
            <div className="apu-t">
              <div className="apt">ACHIEVEMENT UNLOCKED</div>
              <div className="apn">{popup.name}</div>
              <div className="apx">+{popup.xp} XP &middot; {popup.desc}</div>
            </div>
          </div>
        )}

        <Navbar active="achievements" />
      </div>
    </AuthGate>
  );
}
