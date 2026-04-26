'use client';
import React, { useEffect, useState } from 'react';
import { useAuth } from '@/hooks/useAuth';
import { useTelegram } from '@/hooks/useTelegram';
import { useTradingMode } from '@/components/TradingModeContext';
import Header from '@/components/Header';
import Navbar from '@/components/Navbar';
import Link from 'next/link';
import AuthGate from '@/components/AuthGate';
import { getFullWallet, getTrades, getUserStats, getBridgeHistory, getPretiumTransactions, BASE, authFetch } from '@/lib/api';

export default function ProfilePage() {
  const { user, walletAddress, logout, isLoggingOut } = useAuth();
  const { haptic } = useTelegram();
  const { mode } = useTradingMode();
  const isReal = mode === 'real';

  const [wallet, setWallet]         = useState(null);
  const [trades, setTrades]         = useState([]);
  const [stats, setStats]           = useState(null);
  const [bridges, setBridges]       = useState([]);
  const [pretiumTxs, setPretiumTxs]  = useState([]);
  const [loading, setLoading]       = useState(true);

  const [dbUsername, setDbUsername]   = useState('');
  const [editingName, setEditingName] = useState(false);
  const [newUsername, setNewUsername] = useState('');
  const [savingName, setSavingName]   = useState(false);
  const [saveError, setSaveError]     = useState('');

  useEffect(() => {
    if (!walletAddress) return;
    authFetch(`${BASE}/api/wallet/connect`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ wallet_address: walletAddress.toLowerCase() }),
    })
      .then(r => r.json())
      .then(data => {
        if (data?.username) {
          setDbUsername(data.username);
          try { window.localStorage.setItem('nort_username', data.username); } catch {}
        }
      })
      .catch(() => {});
  }, [walletAddress]);

  useEffect(() => {
    if (!walletAddress) return;
    
    // Load sequentially rather than Promise.all to prevent flooding the backend authentication rate limits (429 -> 401 proxy issue)
    const loadData = async () => {
      try {
        const w = await getFullWallet(); setWallet(w);
        const t = await getTrades(); setTrades(t);
        const s = await getUserStats(); setStats(s);
        const b = await getBridgeHistory(); setBridges(b.bridges || []);
        const f = await getPretiumTransactions(null, 5); setPretiumTxs(f.transactions || []);
      } catch (err) {
        console.warn('Profile sync error:', err);
      } finally {
        setLoading(false);
      }
    };
    
    loadData();
  }, [walletAddress]);

  const saveUsername = async () => {
    if (!newUsername.trim() || !walletAddress) return;
    setSavingName(true); setSaveError('');
    try {
      await authFetch(`${BASE}/api/wallet/connect`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ wallet_address: walletAddress.toLowerCase(), username: newUsername.trim() }),
      });
      setDbUsername(newUsername.trim());
      try { window.localStorage.setItem('nort_username', newUsername.trim()); } catch {}
      setEditingName(false);
    } catch { setSaveError('Could not save. Try again.'); }
    finally { setSavingName(false); }
  };

  const displayName = dbUsername || user?.firstName || user?.name || 'Trader';
  const initials    = displayName.length >= 2 ? displayName.slice(0, 2).toUpperCase() : 'TR';
  const isNewUser   = !dbUsername && !user?.firstName && !user?.name;

  // Use the right trade list based on mode
  const activeTrades   = trades.filter(t => t.status === 'open');
  const closedTrades   = trades.filter(t => t.status === 'closed');
  const wins           = closedTrades.filter(t => (t.pnl || 0) > 0);
  const losses         = closedTrades.filter(t => (t.pnl || 0) < 0);
  const winRate        = closedTrades.length > 0 ? Math.round((wins.length / closedTrades.length) * 100) : 0;
  const totalPnl       = closedTrades.reduce((sum, t) => sum + (t.pnl || 0), 0);

  // Balance to display depends on mode
  const displayBalance = isReal
    ? (wallet?.realBalanceUsdc ?? 0)
    : (wallet?.paperBalance ?? 0);

  const fmt      = n => n >= 0 ? `+$${n.toFixed(2)}` : `-$${Math.abs(n).toFixed(2)}`;
  const pnlColor = n => n > 0 ? 'var(--green)' : n < 0 ? 'var(--red)' : 'inherit';
  const bridgeStatusColor = s => ({ done: 'var(--green)', failed: 'var(--red)', bridging: 'var(--teal)', pending: 'var(--muted)' }[s] || 'var(--muted)');

  return (
    <AuthGate>
      <div className={`app${isReal ? ' real-mode' : ''}`}>
        <Header title="PROFILE" hideLogo={true} />

        <div className="scroll">
          {/* ── Avatar + Name ── */}
          <div className="profile-header fu d1">
            <div className="profile-avatar">{initials}</div>
            {editingName ? (
              <div style={{ width: '100%', marginTop: 8 }}>
                <div className="modal-input-wrap">
                  <input className="modal-input" type="text" placeholder="New username"
                    value={newUsername} onChange={e => setNewUsername(e.target.value)}
                    maxLength={24} onKeyDown={e => e.key === 'Enter' && saveUsername()} autoFocus />
                </div>
                {saveError && <div style={{ color: 'var(--red)', fontSize: 11, marginTop: 4, textAlign: 'center' }}>{saveError}</div>}
                <div style={{ display: 'flex', gap: 8, marginTop: 8, justifyContent: 'center' }}>
                  <button className="modal-cta" onClick={saveUsername} disabled={!newUsername.trim() || savingName} style={{ flex: 1 }}>
                    {savingName ? 'Saving...' : 'Save'}
                  </button>
                  <button className="chip-btn" onClick={() => { setEditingName(false); setSaveError(''); }}>Cancel</button>
                </div>
              </div>
            ) : (
              <>
                <div className="profile-name">{displayName}</div>
                {isNewUser && <div style={{ fontSize: 12, color: 'var(--g3)', marginTop: 4, textAlign: 'center' }}>Set a username to appear on the leaderboard</div>}
                {user?.email && <div className="profile-email">{user.email}</div>}
                <button className="chip-btn" style={{ marginTop: 8 }} onClick={() => { setNewUsername(dbUsername || ''); setEditingName(true); setSaveError(''); }}>
                  ✏ {isNewUser ? 'Set Username' : 'Edit Username'}
                </button>
              </>
            )}
          </div>

          {/* ── Balance Card (mode-aware) ── */}
          <div className="sec-lbl fu d2"><span className="sec-t">Trading Stats</span>
            <span className="sec-t" style={{ color: isReal ? '#F59E0B' : 'var(--teal)', fontSize: 10, fontFamily: 'DM Mono,monospace' }}>
              {isReal ? '⚡ REAL' : '◈ PAPER'}
            </span>
          </div>

          {loading ? (
            <div className="empty"><div className="empty-icon">⟳</div></div>
          ) : (
            <div className="bets-stats fu d3">
              <div className="stat-card" style={{ borderColor: isReal ? 'rgba(245,158,11,0.3)' : undefined }}>
                <span className="stat-label">{isReal ? 'USDC Balance' : 'Balance'}</span>
                <span className="stat-val">${displayBalance.toFixed(isReal ? 2 : 0)}</span>
              </div>
              <div className="stat-card">
                <span className="stat-label">Total P&amp;L</span>
                <span className="stat-val" style={{ color: pnlColor(totalPnl) }}>{fmt(totalPnl)}</span>
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
                {[
                  ['Level', stats.level],
                  ['XP', stats.xp?.toLocaleString()],
                  ['Rank', `#${stats.rank ?? '—'}`],
                  ['Next Level', `${stats.xpToNextLevel} XP to go`],
                ].map(([label, val]) => (
                  <div key={label} className="settings-item">
                    <div className="settings-label">{label}</div>
                    <div className="settings-value">{val}</div>
                  </div>
                ))}
              </div>
            </>
          )}

          {/* ── Bridge History (only in real mode) ── */}
          {isReal && bridges.length > 0 && (
            <>
              <div className="sec-lbl fu d6"><span className="sec-t">Bridge History</span><span className="sec-t">{bridges.length} transactions</span></div>
              <div className="settings-group fu d7">
                {bridges.slice(0, 5).map(b => (
                  <div key={b.id} className="settings-item">
                    <div className="settings-label">
                      ${b.amount_usdc} USDC · {b.from_chain}→{b.to_chain}
                      <div style={{ fontSize: 10, color: 'var(--muted)', marginTop: 2 }}>
                        {new Date(b.created_at).toLocaleDateString()}
                      </div>
                    </div>
                    <div className="settings-value" style={{ color: bridgeStatusColor(b.status), fontFamily: 'DM Mono,monospace', fontSize: 11 }}>
                      {b.status.toUpperCase()}
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}

          {/* ── Open Positions ── */}
          {activeTrades.length > 0 && (
            <>
              <div className="sec-lbl fu d6"><span className="sec-t">Open Positions</span><span className="sec-t">{activeTrades.length} active</span></div>
              {activeTrades.map((t, i) => (
                <div key={t.id} className={`trade-item fu d${Math.min(i+1,6)}`}>
                  <div className={`trade-side-badge ${t.side}`}>{t.side.toUpperCase()}</div>
                  <div className="trade-info">
                    <div className="trade-q">{t.q}</div>
                    <div className="trade-meta">${t.amount} · {(t.price*100).toFixed(0)}¢ entry</div>
                  </div>
                  <div className="trade-pnl" style={{ color: pnlColor(t.pnl) }}>{t.pnl ? fmt(t.pnl) : '—'}</div>
                </div>
              ))}
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
            <div className="empty"><div className="empty-icon">◇</div><div className="empty-text">No closed trades yet</div></div>
          ) : (
            <div style={{ paddingBottom: 8 }}>
              {closedTrades.map((t, i) => (
                <div key={t.id} className={`trade-item fu d${Math.min(i+1,6)}`}>
                  <div className={`trade-side-badge ${t.side}`}>{t.side.toUpperCase()}</div>
                  <div className="trade-info">
                    <div className="trade-q">{t.q}</div>
                    <div className="trade-meta">${t.amount} · {(t.price*100).toFixed(0)}¢ · closed</div>
                  </div>
                  <div className="trade-pnl" style={{ color: pnlColor(t.pnl||0) }}>{fmt(t.pnl||0)}</div>
                </div>
              ))}
            </div>
          )}

          {/* ── Wallet ── */}
          <div className="sec-lbl fu d7"><span className="sec-t">Wallet</span></div>
          <div className="settings-group fu d8">
            <div className="settings-item">
              <div className="settings-label">Address</div>
              <div className="settings-value mono">{walletAddress ? `${walletAddress.slice(0,6)}...${walletAddress.slice(-4)}` : 'Not connected'}</div>
            </div>
            <div className="settings-item">
              <div className="settings-label">Mode</div>
              <div className="settings-value">
                <span className={`chip ${isReal ? 'chip-amber' : 'chip-green'}`}>{isReal ? '⚡ Real Trading' : '◈ Paper Trading'}</span>
              </div>
            </div>
            {isReal && (
              <div className="settings-item">
                <div className="settings-label">USDC Balance</div>
                <div className="settings-value">${(wallet?.realBalanceUsdc ?? 0).toFixed(2)}</div>
              </div>
            )}
          </div>

          {/* ── Deposit / Withdraw Quick Actions ── */}
          {isReal && (
            <div className="fu d8" style={{ display: 'flex', gap: 8, marginTop: 8, marginBottom: 4 }}>
              <Link href="/wallet" style={{
                flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                padding: '14px 0', borderRadius: 'var(--rsm)',
                background: 'var(--teal-dim)', border: '1px solid var(--teal-border)',
                color: 'var(--teal)', fontSize: 13, fontWeight: 600, textDecoration: 'none',
                fontFamily: 'Plus Jakarta Sans, sans-serif',
              }}>
                Deposit / Withdraw
              </Link>
            </div>
          )}

          {/* ── Pretium Transaction History ── */}
          {isReal && pretiumTxs.length > 0 && (
            <>
              <div className="sec-lbl fu d8"><span className="sec-t">M-Pesa Transactions</span><span className="sec-t">{pretiumTxs.length} recent</span></div>
              <div className="settings-group fu d9">
                {pretiumTxs.map(tx => (
                  <div key={tx.transaction_id} className="settings-item">
                    <div className="settings-label">
                      {tx.type === 'onramp' ? 'Deposit' : 'Withdraw'} · {tx.type === 'onramp'
                        ? `KES ${Number(tx.amount_fiat || 0).toLocaleString()}`
                        : `$${Number(tx.amount_crypto || 0).toFixed(2)}`}
                      <div style={{ fontSize: 10, color: 'var(--muted)', marginTop: 2 }}>
                        {tx.created_at ? new Date(tx.created_at).toLocaleDateString() : ''}
                      </div>
                    </div>
                    <div className="settings-value" style={{
                      color: tx.status === 'completed' ? 'var(--green)' : ['failed','expired'].includes(tx.status) ? 'var(--red)' : '#F59E0B',
                      fontFamily: 'DM Mono,monospace', fontSize: 11,
                    }}>
                      {tx.status.toUpperCase()}
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}

          <div className="settings-group fu d9" style={{ marginTop: 8 }}>
            <button className="settings-btn danger" disabled={isLoggingOut} onClick={() => { haptic?.medium?.(); logout(); }}
              style={{ width: '100%', padding: '16px', fontSize: '14px', opacity: isLoggingOut ? 0.7 : 1 }}>
              {isLoggingOut ? 'Logging Out...' : 'Log Out'}
            </button>
          </div>

          <div className="profile-disclaimer fu d10">
            <div className="disclaimer-text">
              {isReal
                ? '⚡ Real trading mode — trades use actual USDC on Base/Polygon'
                : '◈ Paper trading demo · No real funds · All trades simulated'}
            </div>
          </div>
        </div>

        <Navbar active="profile" />
      </div>
    </AuthGate>
  );
}
