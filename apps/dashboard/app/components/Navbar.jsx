'use client';
import { useState } from 'react';
import Link from 'next/link';
import { useAuth } from '@/hooks/useAuth';
import { useAuthGuard } from '@/hooks/useAuthGuard';
import { useTradingMode } from './TradingModeContext';
import ModeToggleModal from './ModeToggleModal';
import AuthRequiredModal from './AuthRequiredModal';

// ── Which routes require authentication ───────────────────────────────────────
// Public routes anyone can visit; everything else will trigger the login modal.
const PUBLIC_ROUTES = new Set(['/', '/signals', '/markets', '/leaderboard']);

// Nav items with human-readable "why you need to login" messages for protected routes
const NAV_ITEMS = [
  {
    href:     '/',
    key:      'feed',
    label:    'Feed',
    public:   true,
    icon: <svg viewBox="0 0 24 24"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>,
  },
  {
    href:     '/signals',
    key:      'signals',
    label:    'Signals',
    public:   true,
    icon: <svg viewBox="0 0 24 24"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>,
  },
  {
    href:     '/leaderboard',
    key:      'leaderboard',
    label:    'Ranks',
    public:   true,
    icon: <svg viewBox="0 0 24 24"><path d="M18 20V10M12 20V4M6 20v-6"/></svg>,
  },
  {
    href:     '/achievements',
    key:      'achievements',
    label:    'Badges',
    public:   false,
    authMsg:  'Connect your wallet to track your achievements and badges.',
    icon: <svg viewBox="0 0 24 24"><circle cx="12" cy="8" r="6"/><path d="M15.477 12.89L17 22l-5-3-5 3 1.523-9.11"/></svg>,
  },
  {
    href:     '/trade',
    key:      'bets',
    label:    'Bets',
    public:   false,
    authMsg:  'Connect your wallet to see your open positions and trade history.',
    icon: <svg viewBox="0 0 24 24"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6"/></svg>,
  },
  {
    href:     '/wallet',
    key:      'wallet',
    label:    'Wallet',
    public:   false,
    authMsg:  'Connect your wallet to deposit, withdraw, and view your balance.',
    icon: <svg viewBox="0 0 24 24"><rect x="2" y="6" width="20" height="14" rx="2"/><path d="M2 10h20"/><circle cx="18" cy="16" r="1"/></svg>,
  },
  {
    href:     '/profile',
    key:      'profile',
    label:    'Profile',
    public:   false,
    authMsg:  'Connect your wallet to view and customize your profile.',
    icon: <svg viewBox="0 0 24 24"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>,
  },
];

// ── Mode pill ─────────────────────────────────────────────────────────────────
function ModePill({ onClick }) {
  const { mode, loading } = useTradingMode();
  if (loading) return null;
  const isReal = mode === 'real';
  return (
    <button
      onClick={onClick}
      title={`Trading mode: ${mode}. Click to switch.`}
      style={{
        display:        'flex',
        alignItems:     'center',
        gap:            5,
        padding:        '3px 10px',
        borderRadius:   20,
        border:         `1.5px solid ${isReal ? '#F59E0B' : 'var(--border)'}`,
        background:     isReal ? 'rgba(245,158,11,0.12)' : 'var(--card)',
        color:          isReal ? '#F59E0B' : 'var(--muted)',
        fontSize:       11,
        fontFamily:     'DM Mono, monospace',
        fontWeight:     600,
        letterSpacing:  '0.04em',
        cursor:         'pointer',
        textTransform:  'uppercase',
        whiteSpace:     'nowrap',
        flexShrink:     0,
        transition:     'all 0.2s',
      }}
    >
      <span style={{
        width:        6,
        height:       6,
        borderRadius: '50%',
        background:   isReal ? '#F59E0B' : 'var(--muted)',
        animation:    isReal ? 'pulse 1.5s infinite' : 'none',
        flexShrink:   0,
      }} />
      {isReal ? 'Real' : 'Paper'}
    </button>
  );
}

// ── NavItem — renders as Link (public) or guarded button (protected) ──────────
function NavItem({ item, active, isAuthed, onGuardedClick, mobile = false }) {
  const isActive = active === item.key;

  if (item.public || isAuthed) {
    // Fully public or already logged in → normal Link
    if (mobile) {
      return (
        <Link href={item.href} className={`nb ${isActive ? 'on' : ''}`}>
          {item.icon}
          {item.label}
        </Link>
      );
    }
    return (
      <Link href={item.href} className={`nav-link ${isActive ? 'on' : ''}`}>
        {item.icon}
        {item.label}
      </Link>
    );
  }

  // Protected + unauthenticated → intercept with modal
  const handleClick = () => onGuardedClick(item.href, item.authMsg);

  if (mobile) {
    return (
      <button
        className={`nb ${isActive ? 'on' : ''}`}
        onClick={handleClick}
        style={{ background: 'none', border: 'none', cursor: 'pointer' }}
        aria-label={`${item.label} — login required`}
      >
        {/* Lock indicator on protected items */}
        <span style={{ position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          {item.icon}
          <span style={{
            position:   'absolute',
            bottom:     -3,
            right:      -4,
            fontSize:   7,
            lineHeight: 1,
            color:      'var(--text-muted)',
          }}>🔒</span>
        </span>
        {item.label}
      </button>
    );
  }

  return (
    <button
      className={`nav-link ${isActive ? 'on' : ''}`}
      onClick={handleClick}
      style={{ background: 'none', border: 'none', cursor: 'pointer' }}
      aria-label={`${item.label} — login required`}
    >
      {item.icon}
      {item.label}
      <span style={{ fontSize: 10, opacity: 0.5, marginLeft: 2 }}>🔒</span>
    </button>
  );
}

// ── Main Navbar ───────────────────────────────────────────────────────────────
export default function Navbar({ active }) {
  const { user, isAuthed } = useAuth();
  const initials = user?.firstName?.slice(0, 2).toUpperCase() || 'NJ';
  const [showModeModal, setShowModeModal] = useState(false);

  const {
    pendingRoute,
    pendingMessage,
    guardedNavigate,
    handleLogin,
    dismiss,
  } = useAuthGuard();

  return (
    <>
      {/* ── MOBILE bottom nav ── */}
      <nav className="nav-mobile">
        {NAV_ITEMS.map(item => (
          <NavItem
            key={item.key}
            item={item}
            active={active}
            isAuthed={isAuthed}
            onGuardedClick={guardedNavigate}
            mobile
          />
        ))}
      </nav>

      {/* ── MOBILE mode pill (fixed above bottom nav) ── */}
      <div
        style={{
          position: 'fixed',
          bottom:   62,
          right:    12,
          zIndex:   90,
          display:  'none',
        }}
        className="mode-pill-mobile"
      >
        <ModePill onClick={() => setShowModeModal(true)} />
      </div>

      {/* ── DESKTOP top nav ── */}
      <nav className="nav-desktop">
        <div className="nav-desktop-inner">
          <Link href="/" className="nav-logo">NORT</Link>

          <div className="nav-links">
            {NAV_ITEMS.filter(i => i.key !== 'profile').map(item => (
              <NavItem
                key={item.key}
                item={item}
                active={active}
                isAuthed={isAuthed}
                onGuardedClick={guardedNavigate}
              />
            ))}
          </div>

          <div className="nav-right">
            <ModePill onClick={() => setShowModeModal(true)} />

            <div className="live-pill">
              <span className="live-dot" />
              Live
            </div>

            {/* Profile: guarded on desktop too */}
            {isAuthed ? (
              <Link
                href="/profile"
                className={`nav-link ${active === 'profile' ? 'on' : ''}`}
                style={{ gap: 8 }}
              >
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
            ) : (
              <button
                className="nav-link"
                onClick={() => guardedNavigate('/profile', 'Connect your wallet to view your profile.')}
                style={{ background: 'none', border: 'none', cursor: 'pointer', gap: 8 }}
              >
                <span style={{
                  width: 22, height: 22, borderRadius: '50%',
                  background: 'var(--glass-bg)',
                  border: '1px solid var(--glass-border)',
                  color: 'var(--text-muted)', display: 'flex', alignItems: 'center',
                  justifyContent: 'center', fontSize: 9,
                  fontFamily: 'DM Mono, monospace', flexShrink: 0,
                }}>
                  ?
                </span>
                Sign In
              </button>
            )}
          </div>
        </div>
      </nav>

      {/* ── Mode toggle modal ── */}
      {showModeModal && <ModeToggleModal onClose={() => setShowModeModal(false)} />}

      {/* ── Auth required modal (shown when guarded route clicked) ── */}
      {pendingRoute && (
        <AuthRequiredModal
          message={pendingMessage}
          onLogin={handleLogin}
          onDismiss={dismiss}
        />
      )}
    </>
  );
}
