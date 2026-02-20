'use client';
import Link from 'next/link';
import { useAuth } from '@/hooks/useAuth';

const NAV_ITEMS = [
  { href: '/', key: 'feed', label: 'Feed', icon: <svg viewBox="0 0 24 24"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg> },
  { href: '/markets', key: 'markets', label: 'Markets', icon: <svg viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg> },
  { href: '/signals', key: 'signals', label: 'Signals', icon: <svg viewBox="0 0 24 24"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg> },
  { href: '/trade', key: 'bets', label: 'Bets', icon: <svg viewBox="0 0 24 24"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6"/></svg> },
  { href: '/profile', key: 'profile', label: 'Profile', icon: <svg viewBox="0 0 24 24"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg> },
];

export default function Navbar({ active }) {
  const { user } = useAuth();
  const initials = user?.firstName?.slice(0,2).toUpperCase() || 'NJ';

  return (
    <>
      {/* ── MOBILE bottom nav ── */}
      <nav className="nav-mobile">
        {NAV_ITEMS.map(item => (
          <Link key={item.key} href={item.href} className={`nb ${active === item.key ? 'on' : ''}`}>
            {item.icon}
            {item.label}
          </Link>
        ))}
      </nav>

      {/* ── DESKTOP top nav (glassmorphism) ── */}
      <nav className="nav-desktop">
        <div className="nav-desktop-inner">
          {/* Logo */}
          <Link href="/" className="nav-logo">NORT</Link>

          {/* Nav links */}
          <div className="nav-links">
            {NAV_ITEMS.filter(i => i.key !== 'profile').map(item => (
              <Link key={item.key} href={item.href} className={`nav-link ${active === item.key ? 'on' : ''}`}>
                {item.icon}
                {item.label}
              </Link>
            ))}
          </div>

          {/* Right side */}
          <div className="nav-right">
            <div className="live-pill">
              <span className="live-dot" />
              Live
            </div>
            <Link href="/profile" className={`nav-link ${active === 'profile' ? 'on' : ''}`} style={{ gap: 8 }}>
              <span style={{ width: 22, height: 22, borderRadius: '50%', background: active === 'profile' ? 'rgba(255,255,255,0.2)' : 'var(--black)', color: 'var(--white)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 9, fontFamily: 'DM Mono, monospace', flexShrink: 0 }}>
                {initials}
              </span>
              Profile
            </Link>
          </div>
        </div>
      </nav>
    </>
  );
}
