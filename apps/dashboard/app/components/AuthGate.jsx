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
  const { ready: privyReady, isAuthed } = useAuth();
  const { user: tgUser, ready: tgReady } = useTelegram();
  const [redirected, setRedirected] = useState(false);

  const isReady  = privyReady && tgReady;
  const loggedIn = isAuthed || !!tgUser;

  // Hard gate redirect — runs after mount, no router context needed
  useEffect(() => {
    if (softGate || !isReady || loggedIn || redirected) return;
    setRedirected(true);
    const from = encodeURIComponent(window.location.pathname);
    window.location.replace(`/login?from=${from}`);
  }, [softGate, isReady, loggedIn, redirected]);

  // Soft gate — always render children, actions protected inline
  if (softGate) return <>{children}</>;

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
