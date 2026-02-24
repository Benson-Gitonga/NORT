'use client';
import React from 'react';
import { useAuth } from '@/hooks/useAuth';
import { useTelegram } from '@/hooks/useTelegram';
import AuthGate from '@/components/AuthGate';
import Navbar from '@/components/Navbar';

export default function ProfilePage() {
  const { user, walletAddress, logout } = useAuth();
  const { haptic } = useTelegram();

  const displayName = user?.firstName || user?.name || user?.displayName || 'User';
  const displayUsername = user?.email?.split('@')[0] || '';

  const handleLogout = () => {
    haptic?.medium?.();
    logout();
  };

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

  const initials = getInitials(displayName);

  return (
    <AuthGate>
      <div className="app">
        <div className="header">
          <div className="header-logo">Profile</div>
          <div className="header-right">
            <div className="live-pill">
              <span className="live-dot" />
              Live
            </div>
          </div>
        </div>

        <div className="scroll">
          <div className="profile-header fu d1">
            <div className="profile-avatar">{initials}</div>
            <div className="profile-name">{displayName}</div>
            <div className="profile-email">
              {displayUsername ? '@' + displayUsername : (user?.email || 'Paper Trading')}
            </div>
          </div>

          <div className="sec-lbl fu d2">
            <span className="sec-t">Account</span>
          </div>

          <div className="settings-group fu d3">
            {user?.email && (
              <div className="settings-item">
                <div className="settings-label">Email</div>
                <div className="settings-value">{user.email}</div>
              </div>
            )}
            {user?.id && (
              <div className="settings-item">
                <div className="settings-label">User ID</div>
                <div className="settings-value mono">{user.id.slice(0, 12)}...</div>
              </div>
            )}
          </div>

          <div className="sec-lbl fu d4">
            <span className="sec-t">Wallet</span>
          </div>

          <div className="settings-group fu d5">
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

          <div className="sec-lbl fu d6">
            <span className="sec-t">Session</span>
          </div>

          <div className="settings-group fu d7">
            <button
              className="settings-btn danger"
              onClick={handleLogout}
              style={{ width: '100%', padding: '16px', fontSize: '14px' }}
            >
              <svg viewBox="0 0 24 24" style={{ width: 18, height: 18 }}>
                <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4" />
                <polyline points="16 17 21 12 16 7" />
                <line x1="21" y1="12" x2="9" y2="12" />
              </svg>
              Log Out
            </button>
          </div>

          <div className="profile-disclaimer fu d8">
            <div className="disclaimer-icon">warning</div>
            <div className="disclaimer-text">
              This is a paper trading demo. No real funds are involved. All trades are simulated.
            </div>
          </div>
        </div>

        <Navbar active="profile" />
      </div>
    </AuthGate>
  );
}
