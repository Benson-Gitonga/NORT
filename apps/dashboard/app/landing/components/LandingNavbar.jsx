'use client';
import { useState } from 'react';
import { usePrivy } from '@privy-io/react-auth';

export default function LandingNavbar() {
  const [menuOpen, setMenuOpen] = useState(false);
  const { login, authenticated, ready } = usePrivy();

  return (
    <header className="l-nav-blur" style={{ position:'fixed', top:0, left:0, right:0, zIndex:50 }}>
      <div style={{ maxWidth:1152, margin:'0 auto', padding:'0 24px', height:64, display:'flex', alignItems:'center', justifyContent:'space-between' }}>

        <a href="#" className="l-nav-logo" aria-label="NORT homepage">NORT</a>

        {/* Desktop nav */}
        <nav style={{ display:'flex', alignItems:'center', gap:32 }} className="hidden-mobile-l" aria-label="Main navigation">
          <a href="#l-features"     className="l-nav-link">Features</a>
          <a href="#l-how-it-works" className="l-nav-link">How it works</a>
          <a href="#l-nort-bot"     className="l-nav-link">Nort Bot</a>
          <a href="#l-pricing"      className="l-nav-link">Pricing</a>
        </nav>

        <div style={{ display:'flex', alignItems:'center', gap:10 }}>
          <a href="https://docs-nortapp.online" target="_blank" rel="noopener noreferrer"
            className="l-btn l-btn-ghost" style={{ padding:'8px 18px', fontSize:13 }}>Docs</a>
          <button
            className="l-btn l-btn-primary"
            style={{ padding:'8px 18px', fontSize:13, border:'none', cursor:'pointer' }}
            onClick={login}
            disabled={!ready}
          >
            {ready && authenticated ? 'Go to App' : 'Start Trading Free'}
          </button>
          {/* Hamburger */}
          <button
            className="hidden-desktop-l"
            aria-label={menuOpen ? 'Close menu' : 'Open menu'}
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen(!menuOpen)}
            style={{ display:'none', flexDirection:'column', justifyContent:'center', alignItems:'center',
              gap:5, width:36, height:36, background:'none', border:'1px solid var(--border)',
              borderRadius:8, cursor:'pointer', padding:8 }}
          >
            <span style={{ width:16, height:1.5, background: menuOpen ? 'var(--accent)' : 'var(--text-3)', borderRadius:2, transition:'all .2s', transform: menuOpen ? 'rotate(45deg) translate(5px,5px)' : 'none' }} />
            <span style={{ width:16, height:1.5, background: menuOpen ? 'transparent' : 'var(--text-3)', borderRadius:2, transition:'all .2s' }} />
            <span style={{ width:16, height:1.5, background: menuOpen ? 'var(--accent)' : 'var(--text-3)', borderRadius:2, transition:'all .2s', transform: menuOpen ? 'rotate(-45deg) translate(5px,-5px)' : 'none' }} />
          </button>
        </div>
      </div>
      {menuOpen && (
        <nav style={{ display:'flex', flexDirection:'column', padding:'12px 24px 20px',
          background:'rgba(5,8,18,0.98)', borderTop:'1px solid var(--border)' }}>
          {[['#l-features','Features'],['#l-how-it-works','How it works'],['#l-nort-bot','Nort Bot'],['#l-pricing','Pricing']].map(([href,label]) => (
            <a key={href} href={href} className="l-nav-link" onClick={() => setMenuOpen(false)}
              style={{ padding:'14px 0', borderBottom:'1px solid var(--border)', fontSize:15 }}>{label}</a>
          ))}
        </nav>
      )}
    </header>
  );
}
