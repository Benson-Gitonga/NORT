'use client';
import React, { useEffect, useState } from 'react';
import { useAuth } from '@/hooks/useAuth';
import { useTelegram } from '@/hooks/useTelegram';
import AuthGate from '@/components/AuthGate';
import Navbar from '@/components/Navbar';
import { getWallet, getTrades, getUserStats, BASE } from '@/lib/api';

export default function ProfilePage() {
  const { user, walletAddress, logout } = useAuth();
  const { haptic } = useTelegram();

  const [wallet, setWallet]   = useState(null);
  const [trades, setTrades]   = useState([]);
  const [stats, setStats]     = useState(null);
  const [loading, setLoading] = useState(true);

  // Username editing
  const [editingName, setEditingName]   = useState(false);
  const [newUsername, setNewUsername]   = useState('');
  const [savingName, setSavingName]     = useState(false);
  const [savedUsername, setSavedUsername] = useState('');

  useEffect(() => {
    Promise.all([getWallet(), getTrades(), getUserStats()])
      .then(([w, t, s]) => { setWallet(w); setTrades(t); setStats(s); })
      .catch(console.warn)
      .finally(() => setLoading(false));
  }, []);

  // Auto-register wallet in DB so username save & trades work
  useEffect(() => {
    if (!walletAddress) return;
    fetch(`${BASE}/api/wallet/connect`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        wallet_address: walletAddress,
        telegram_id:   walletAddress.toLowerCase(),
      }),
    }).catch(() => {});
  }, [walletAddress]);

  const handleLogout = () => { haptic?.medium?.(); logout(); };

  const formatAddress = (addr) => {
    if (!addr) return 'Not connected';
    return addr.slice(0, 6) + '...' + addr.slice(-4);
  };

  const getInitials = (name) => {
    if (!name) return 'U';
    const parts = name.split(' ').filter(p => p.length > 0);
    if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
    return name.slice(0, 2).toUpperCase();
  };

  const saveUsername = async () => {
    if (!newUsername.trim() || !walletAddress) return;
    setSavingName(true);
    try {
      await fetch(`${BASE}/api/wallet/connect`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          wallet_address: walletAddress,
          telegram_id:   walletAddress.toLowerCase(),
          username:      newUsername.trim(),
        }),
      });
      setSavedUsername(newUsername.trim());
      setEditingName(false);
    } catch (e) {
      console.warn('username save failed:', e);
    } finally {
      setSavingName(false);
    }
  };

  const displayName = savedUsername || user?.firstName || user?.name || 'Trader';
  const initials    = getInitials(displayName);

  // Computed trade stats
  const closedTrades  = trades.filter(t => t.status === 'closed');
  const wins          = closedTrades.filter(t => (t.pnl || 0) > 0);
  const losses        = closedTrades.filter(t => (t.pnl || 0) < 0);
  const winRate       = closedTrades.length > 0
    ? Math.round((wins.length / closedTrades.length) * 100)
    : 0;
  const totalPnl      = closedTrades.reduce((sum, t) => sum + (t.pnl || 0), 0);
  const openTrades    = trades.filter(t => t.status === 'open');

  const fmt     = (n) => (n >= 0 ? `+$${n.toFixed(2)}` : `-$${Math.abs(n).toFixed(2)}`);
  const pnlColor = (n) => n > 0 ? 'var(--green)' : n < 0 ? 'var(--red)' : 'inherit';

  return (
    <AuthGate>
      <div className="app">
        <div className="header">
          <div className="header-logo">Profile</div>
          <div className="header-right">
            <div className="live-pill"><span className="live-dot" />Paper</div>
          </div>
        </div>

        <div className="scroll">
          {/* ── Avatar + Name ── */}
          <div className="profile-header fu d1">
            <div className="profile-avatar">{initials}</div>
            <div className="profile-name">{displayName}</div>
            {user?.email && (
              <div className="profile-email">{user.email}</div>
            )}
            <button
              className="chip-btn"
              style={{ marginTop: 8 }}
              onClick={() => { setNewUsername(''); setEditingName(true); }}
            >
              ✏ Edit Username
            </button>
          </div>

          {/* Username editor */}
          {editingName && (
            <div className="settings-group fu d2" style={{ padding: 16 }}>
              <div className="modal-input-wrap">
                <input
                  className="modal-input"
                  type="text"
                  placeholder="New username"
                  value={newUsername}
                  onChange={e => setNewUsername(e.target.value)}
                  maxLength={24}
                  onKeyDown={e => e.key === 'Enter' && saveUsername()}
                  autoFocus
                />
              </div>
              <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                <button className="modal-cta" onClick={saveUsername} disabled={!newUsername.trim() || savingName}>
                  {savingName ? 'Saving...' : 'Save'}
                </button>
                <button className="chip-btn" onClick={() => setEditingName(false)}>Cancel</button>
              </div>
            </div>
          )}

          {/* ── Stats row ── */}
          <div className="sec-lbl fu d2"><span className="sec-t">Trading Stats</span></div>
          {loading ? (
            <div className="empty"><div className="empty-icon">⟳</div></div>
          ) : (
            <div className="bets-stats fu d3">
              <div className="stat-card">
                <span className="stat-label">Balance</span>
                <span className="stat-val">${wallet?.balance?.toFixed(0) ?? '1000'}</span>
              </div>
              <div className="stat-card">
                <span className="stat-label">Total P&amp;L</span>
                <span className="stat-val" style={{ color: pnlColor(totalPnl) }}>
                  {fmt(totalPnl)}
                </span>
              </div>
              <div className="stat-card">
                <span className="stat-label">Win Rate</span>
                <span className="stat-val">{winRate}%</span>
              </div>
              <div className="stat-card">
                <span className="stat-label">Streak</span>
                <span className="stat-val">🔥 {stats?.streak ?? 0}</span>
              </div>
              <div className="stat-card">
                <span className="stat-label">Wins</span>
                <span className="stat-val" style={{ color: 'var(--green)' }}>{wins.length}</span>
              </div>
              <div className="stat-card">
                <span className="stat-label">Losses</span>
                <span className="stat-val" style={{ color: 'var(--red)' }}>{losses.length}</span>
              </div>
            </div>
          )}

          {/* ── XP / Level ── */}
          {stats && (
            <>
              <div className="sec-lbl fu d4"><span className="sec-t">Level & XP</span></div>
              <div className="settings-group fu d5">
                <div className="settings-item">
                  <div className="settings-label">Level</div>
                  <div className="settings-value">{stats.level}</div>
                </div>
                <div className="settings-item">
                  <div className="settings-label">XP</div>
                  <div className="settings-value">{stats.xp?.toLocaleString()}</div>
                </div>
                <div className="settings-item">
                  <div className="settings-label">Rank</div>
                  <div className="settings-value">#{stats.rank ?? '—'}</div>
                </div>
                <div className="settings-item">
                  <div className="settings-label">Next Level</div>
                  <div className="settings-value">{stats.xpToNextLevel} XP to go</div>
                </div>
              </div>
            </>
          )}

          {/* ── Open Positions ── */}
          {openTrades.length > 0 && (
            <>
              <div className="sec-lbl fu d6">
                <span className="sec-t">Open Positions</span>
                <span className="sec-t">{openTrades.length} active</span>
              </div>
              <div style={{ paddingBottom: 4 }}>
                {openTrades.map((t, i) => (
                  <div key={t.id} className={`trade-item fu d${Math.min(i + 1, 6)}`}>
                    <div className={`trade-side-badge ${t.side}`}>{t.side.toUpperCase()}</div>
                    <div className="trade-info">
                      <div className="trade-q">{t.q}</div>
                      <div className="trade-meta">${t.amount} · {(t.price * 100).toFixed(0)}¢ entry</div>
                    </div>
                    <div className="trade-pnl" style={{ color: pnlColor(t.pnl) }}>
                      {t.pnl ? fmt(t.pnl) : '—'}
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}

          {/* ── Trade History ── */}
          <div className="sec-lbl fu d6">
            <span className="sec-t">Trade History</span>
            <span className="sec-t">{closedTrades.length} closed</span>
          </div>
          {loading ? (
            <div className="empty"><div className="empty-icon">⟳</div></div>
          ) : closedTrades.length === 0 ? (
            <div className="empty">
              <div className="empty-icon">◇</div>
              <div className="empty-text">No closed trades yet</div>
            </div>
          ) : (
            <div style={{ paddingBottom: 8 }}>
              {closedTrades.map((t, i) => (
                <div key={t.id} className={`trade-item fu d${Math.min(i + 1, 6)}`}>
                  <div className={`trade-side-badge ${t.side}`}>{t.side.toUpperCase()}</div>
                  <div className="trade-info">
                    <div className="trade-q">{t.q}</div>
                    <div className="trade-meta">${t.amount} · {(t.price * 100).toFixed(0)}¢ · closed</div>
                  </div>
                  <div className="trade-pnl" style={{ color: pnlColor(t.pnl || 0) }}>
                    {fmt(t.pnl || 0)}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* ── Wallet ── */}
          <div className="sec-lbl fu d7"><span className="sec-t">Wallet</span></div>
          <div className="settings-group fu d8">
            <div className="settings-item">
              <div className="settings-label">Address</div>
              <div className="settings-value mono">{formatAddress(walletAddress)}</div>
            </div>
            <div className="settings-item">
              <div className="settings-label">Mode</div>
              <div className="settings-value">
                <span className="chip chip-green">Paper Trading</span>
              </div>
            </div>
          </div>

          {/* ── Logout ── */}
          <div className="settings-group fu d9" style={{ marginTop: 8 }}>
            <button className="settings-btn danger" onClick={handleLogout}
              style={{ width: '100%', padding: '16px', fontSize: '14px' }}>
              Log Out
            </button>
          </div>

          <div className="profile-disclaimer fu d10">
            <div className="disclaimer-text">
              Paper trading demo · No real funds · All trades are simulated
            </div>
          </div>
        </div>

        <Navbar active="profile" />
      </div>
    </AuthGate>
  );
}
