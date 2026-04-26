'use client';
/**
 * AuthGate — client-side route protection.
 *
 * Deliberately avoids useRouter / usePathname at module level.
 * Those hooks can fail if the component mounts before the Next.js
 * router context is ready (e.g. during Privy's lazy-load window),
 * which caused the "AuthGate is not defined" runtime error.
 *
 * Instead we read window.location directly — always available,
 * no context dependency, no hydration timing issues.
 *
 * TWO MODES:
 *   <AuthGate>          Hard gate — must be logged in to see content.
 *   <AuthGate softGate> Soft gate — content visible, actions protected.
 */
import { useEffect, useState } from 'react';
import { useAuth } from '@/hooks/useAuth';
import { useTelegram } from '@/hooks/useTelegram';

export default function AuthGate({ children, softGate = false }) {
  const { ready: privyReady, isAuthed, login } = useAuth();
  const { user: tgUser, ready: tgReady } = useTelegram();
  const [redirected, setRedirected] = useState(false);
  const [sessionExpired, setSessionExpired] = useState(false);

  const isReady  = privyReady && tgReady;
  const loggedIn = isAuthed || !!tgUser;

  // Listen for fatal 401 events globally
  useEffect(() => {
    const handleExpired = () => {
      setSessionExpired(true);
      try { login?.(); } catch {}
    };
    window.addEventListener('session_expired', handleExpired);
    return () => window.removeEventListener('session_expired', handleExpired);
  }, [login]);

  // Clear session-expired guard after a successful login.
  useEffect(() => {
    if (loggedIn) setSessionExpired(false);
  }, [loggedIn]);

  // Hard gate redirect — runs after mount, no router context needed
  useEffect(() => {
    if (softGate || !isReady || loggedIn || redirected || sessionExpired) return;
    setRedirected(true);
    const from = encodeURIComponent(window.location.pathname);
    window.location.replace(`/login?from=${from}`);
  }, [softGate, isReady, loggedIn, redirected, sessionExpired]);

  // Soft gate — always render children, actions protected inline
  if (softGate) return <>{children}</>;

  // Session expired UX lockout
  if (sessionExpired) {
    return (
      <div className="auth-screen" style={{ flexDirection: 'column', padding: 20, textAlign: 'center' }}>
        <div className="auth-logo" style={{ marginBottom: 20 }}>NORT</div>
        <h3 style={{ color: 'var(--red)', fontSize: 18, marginBottom: 10 }}>Session Expired</h3>
        <p style={{ color: 'var(--muted)', fontSize: 13, marginBottom: 20 }}>
          Your authentication token was rejected by the server. Please reconnect your wallet.
        </p>
        <button className="settings-btn" onClick={() => login?.()}>Reconnect Wallet</button>
      </div>
    );
  }

  // Still initialising
  if (!isReady) {
    return (
      <div className="auth-screen">
        <div className="auth-logo">NORT</div>
        <div style={{
          fontSize: 11,
          fontFamily: "'DM Mono', monospace",
          color: 'rgba(255,255,255,0.35)',
          marginTop: 12,
        }}>
          Loading…
        </div>
      </div>
    );
  }

  // Not logged in — blank screen while window.location.replace fires
  if (!loggedIn) {
    return (
      <div className="auth-screen">
        <div className="auth-logo">NORT</div>
      </div>
    );
  }

  // Authenticated ✓
  return <>{children}</>;
}
