'use client';
import { useState } from 'react';
import Link from 'next/link';
import { useAuth } from '@/hooks/useAuth';
import { useTradingMode } from './TradingModeContext';
import ModeToggleModal from './ModeToggleModal';
import { useTier } from '@/hooks/useTier';

const NAV_ITEMS = [
  { href: '/', key: 'feed', label: 'Feed', icon: <svg viewBox="0 0 24 24"><line x1="3" y1="6" x2="21" y2="6" /><line x1="3" y1="12" x2="21" y2="12" /><line x1="3" y1="18" x2="21" y2="18" /></svg> },
  { href: '/signals', key: 'signals', label: 'Signals', icon: <svg viewBox="0 0 24 24"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12" /></svg> },
  { href: '/leaderboard', key: 'leaderboard', label: 'Ranks', icon: <svg viewBox="0 0 24 24"><path d="M18 20V10M12 20V4M6 20v-6" /></svg> },
  { href: '/achievements', key: 'achievements', label: 'Badges', icon: <svg viewBox="0 0 24 24"><circle cx="12" cy="8" r="6" /><path d="M15.477 12.89L17 22l-5-3-5 3 1.523-9.11" /></svg> },
  { href: '/trade', key: 'bets', label: 'Bets', icon: <svg viewBox="0 0 24 24"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6" /></svg> },
  { href: '/wallet', key: 'wallet', label: 'Wallet', icon: <svg viewBox="0 0 24 24"><rect x="2" y="6" width="20" height="14" rx="2" /><path d="M2 10h20" /><circle cx="18" cy="16" r="1" /></svg> },
  { href: '/profile', key: 'profile', label: 'Profile', icon: <svg viewBox="0 0 24 24"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2" /><circle cx="12" cy="7" r="4" /></svg> },
];

function NavIcon({ navKey }) {
  const item = NAV_ITEMS.find(i => i.key === navKey);
  if (!item) return null;
  return (
    <svg 
      viewBox="0 0 24 24" 
      fill="none" 
      stroke="currentColor" 
      strokeWidth="2" 
      strokeLinecap="round" 
      strokeLinejoin="round"
      className="nav-icon"
      style={{ width: 20, height: 20 }}
    >
      {item.icon.props.children}
    </svg>
  );
}

// ── Mode pill — shown on both mobile and desktop navbars ──────────────────────
// Paper = blue/grey, Real = amber with pulse dot
function ModePill({ onClick }) {
  const { mode, loading } = useTradingMode();
  if (loading) return null;
  const isReal = mode === 'real';
  return (
    <button
      onClick={onClick}
      title={`Trading mode: ${mode}. Click to switch.`}
      style={{
        display: 'flex', alignItems: 'center', gap: 5,
        padding: '3px 10px', borderRadius: 20,
        border: `1.5px solid ${isReal ? '#F59E0B' : 'var(--border)'}`,
        background: isReal ? 'rgba(245,158,11,0.12)' : 'var(--card)',
        color: isReal ? '#F59E0B' : 'var(--muted)',
        fontSize: 11, fontFamily: 'DM Mono, monospace', fontWeight: 600,
        letterSpacing: '0.04em', cursor: 'pointer', textTransform: 'uppercase',
        whiteSpace: 'nowrap', flexShrink: 0, transition: 'all 0.2s',
      }}
    >
      <span style={{
        width: 6, height: 6, borderRadius: '50%',
        background: isReal ? '#F59E0B' : 'var(--muted)',
        animation: isReal ? 'pulse 1.5s infinite' : 'none',
        flexShrink: 0,
      }} />
      {isReal ? 'Real' : 'Paper'}
    </button>
  );
}

function TierBadge() {
  const { tier, remaining, loading, FREE_DAILY_LIMIT } = useTier();
  if (loading) return null;
  const isPremium = tier === 'premium';
  return (
    <div
      title={isPremium ? 'Premium access' : `${remaining} free advice calls remaining today`}
      style={{
        display: 'flex', alignItems: 'center', gap: 5,
        padding: '3px 10px', borderRadius: 20,
        border: `1.5px solid ${isPremium ? '#F59E0B' : 'var(--border)'}`,
        background: isPremium ? 'rgba(245,158,11,0.12)' : 'var(--card)',
        color: isPremium ? '#F59E0B' : 'var(--muted)',
        fontSize: 11, fontFamily: 'DM Mono, monospace', fontWeight: 600,
        letterSpacing: '0.04em', textTransform: 'uppercase',
        whiteSpace: 'nowrap', flexShrink: 0, userSelect: 'none',
      }}
    >
      {isPremium ? '⚡ PREMIUM' : `FREE · ${remaining ?? 0}/${FREE_DAILY_LIMIT}`}
    </div>
  );
}

export default function Navbar({ active }) {
  const { user } = useAuth();
  const initials = user?.firstName?.slice(0, 2).toUpperCase() || 'NJ';
  const [showModal, setShowModal] = useState(false);

  return (
    <>
      <nav className="nav-mobile">
        {NAV_ITEMS.map(item => (
          <Link key={item.key} href={item.href} className={`nb ${active === item.key ? 'on' : ''}`}>
            <NavIcon navKey={item.key} />
            {item.label}
          </Link>
        ))}
      </nav>

      <div style={{ position: 'fixed', bottom: 62, right: 12, zIndex: 90, display: 'none' }} className="mode-pill-mobile">
        <ModePill onClick={() => setShowModal(true)} />
      </div>

      <nav className="nav-desktop">
        <div className="nav-desktop-inner">
          <Link href="/" className="nav-logo">NORT</Link>

          <div className="nav-links">
            {NAV_ITEMS.filter(i => i.key !== 'profile').map(item => (
              <Link key={item.key} href={item.href} className={`nav-link ${active === item.key ? 'on' : ''}`}>
                <NavIcon navKey={item.key} />
                {item.label}
              </Link>
            ))}
          </div>

          <div className="nav-right">
            <TierBadge />
            <ModePill onClick={() => setShowModal(true)} />
            <div className="live-pill">
              <span className="live-dot" />
              Live
            </div>
            <Link href="/profile" className={`nav-link ${active === 'profile' ? 'on' : ''}`} style={{ gap: 8 }}>
              <span style={{
                width: 22, height: 22, borderRadius: '50%',
                background: active === 'profile' ? 'rgba(255,255,255,0.2)' : 'var(--black)',
                color: 'var(--white)', display: 'flex', alignItems: 'center',
                justifyContent: 'center', fontSize: 9,
                fontFamily: 'DM Mono, monospace', flexShrink: 0,
              }}>
                {initials}
              </span>
              Profile
            </Link>
          </div>
        </div>
      </nav>

      {showModal && <ModeToggleModal onClose={() => setShowModal(false)} />}
    </>
  );
}
