'use client';
import { useState } from 'react';

export default function Navbar() {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <header className="fixed top-0 inset-x-0 z-50 nav-blur">
      <div style={{ maxWidth:1152, margin:'0 auto', padding:'0 24px', height:64, display:'flex', alignItems:'center', justifyContent:'space-between' }}>

        <a href="#" className="nav-logo" aria-label="NORT — go to homepage">
          NORT
        </a>

        {/* Desktop nav — hidden on mobile */}
        <nav style={{ display:'flex', alignItems:'center', gap:32 }} className="hidden-mobile" aria-label="Main navigation">
          <a href="#features"     className="nav-link">Features</a>
          <a href="#how-it-works" className="nav-link">How it works</a>
          <a href="#nort-bot"     className="nav-link">Nort Bot</a>
          <a href="#pricing"      className="nav-link">Pricing</a>
        </nav>

        <div style={{ display:'flex', alignItems:'center', gap:10 }}>
          {/* Docs link */}
          <a href="https://docs.nortapp.online/" target="_blank" rel="noopener noreferrer" className="btn btn-ghost" style={{ padding:'8px 18px', fontSize:13 }}>Docs</a>
          {/* CTA — always visible */}
          <a href="https://nort-rho.vercel.app" className="btn btn-primary" style={{ padding:'8px 18px', fontSize:13 }}>Start Trading Free</a>

          {/* Hamburger — mobile only */}
          <button
            className="hamburger hidden-desktop"
            aria-label={menuOpen ? 'Close menu' : 'Open menu'}
            aria-expanded={menuOpen}
            aria-controls="mobile-nav"
            onClick={() => setMenuOpen(!menuOpen)}
            style={{
              display:'none', flexDirection:'column', justifyContent:'center',
              alignItems:'center', gap:5, width:36, height:36,
              background:'none', border:'1px solid var(--border)',
              borderRadius:8, cursor:'pointer', padding:8,
            }}
          >
            <span style={{ width:16, height:1.5, background: menuOpen ? 'var(--accent)' : 'var(--text-3)', borderRadius:2, transition:'all .2s', transform: menuOpen ? 'rotate(45deg) translate(5px, 5px)' : 'none' }} />
            <span style={{ width:16, height:1.5, background: menuOpen ? 'transparent' : 'var(--text-3)', borderRadius:2, transition:'all .2s' }} />
            <span style={{ width:16, height:1.5, background: menuOpen ? 'var(--accent)' : 'var(--text-3)', borderRadius:2, transition:'all .2s', transform: menuOpen ? 'rotate(-45deg) translate(5px, -5px)' : 'none' }} />
          </button>
        </div>
      </div>

      {/* Mobile nav dropdown */}
      {menuOpen && (
        <nav
          id="mobile-nav"
          aria-label="Mobile navigation"
          style={{
            display:'flex', flexDirection:'column',
            padding:'12px 24px 20px',
            background:'rgba(5,8,18,0.98)',
            borderTop:'1px solid var(--border)',
          }}
        >
          {[
            ['#features',     'Features'],
            ['#how-it-works', 'How it works'],
            ['#nort-bot',     'Nort Bot'],
            ['#pricing',      'Pricing'],
          ].map(([href, label]) => (
            <a
              key={href}
              href={href}
              className="nav-link"
              onClick={() => setMenuOpen(false)}
              style={{ padding:'14px 0', borderBottom:'1px solid var(--border)', fontSize:15 }}
            >
              {label}
            </a>
          ))}
        </nav>
      )}
    </header>
  );
}
