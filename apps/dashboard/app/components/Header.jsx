'use client';
import React, { useState } from 'react';
import Link from 'next/link';
import { useAuth } from '@/hooks/useAuth';
import { useTradingMode } from './TradingModeContext';
import ModeToggleModal from './ModeToggleModal';

export default function Header({ title = 'NORT', backHref = null, hideLogo = false }) {
  const { user, isAuthed } = useAuth();
  const { mode } = useTradingMode();
  const [showModeModal, setShowModeModal] = useState(false);
  const initials = user?.firstName?.slice(0, 2).toUpperCase() || 'NJ';

  const isReal = mode === 'real';

  return (
    <>
      <div className="header-main">
        {/* Left Section: Logo or Back + Title */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          {!hideLogo && (
            <>
              {backHref && (
                <Link href={backHref} className="m-back-btn" style={{ width: '32px', height: '32px' }}>
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M19 12H5M12 19l-7-7 7-7"/></svg>
                </Link>
              )}
              <Link href="/" className="header-logo" style={{ 
                fontFamily: 'Syne', 
                fontWeight: 800, 
                fontSize: '24px', 
                color: '#fff', 
                textDecoration: 'none',
                letterSpacing: '-1px'
              }}>
                {title}
              </Link>
            </>
          )}
        </div>

        <div className="header-right">
          {/* Paper Trading Toggle */}
          <div 
            className={`mode-toggle-pill ${mode === 'paper' ? 'on' : 'real'}`} 
            onClick={() => setShowModeModal(true)}
          >
            <span className="mode-toggle-label">
              {mode === 'paper' ? 'Paper trading' : 'Real trading'}
            </span>
            <div className="switch-track">
              <div className="switch-thumb" />
            </div>
          </div>

          {/* Search Icon */}
          <button style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'rgba(255,255,255,0.4)', padding: 0, display: 'flex', alignItems: 'center' }}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
          </button>

          {/* Profile Initials */}
          <Link href="/profile" className="user-av" style={{
            width: '32px', height: '32px', borderRadius: '50%',
            background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(132, 130, 130, 0.2)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: '11px', fontWeight: 600, color: '#fff', textDecoration: 'none',
            fontFamily: 'DM Mono'
          }}>
            {isAuthed ? initials : '?'}
          </Link>
        </div>
      </div>

      {showModeModal && <ModeToggleModal onClose={() => setShowModeModal(false)} />}
    </>
  );
}
