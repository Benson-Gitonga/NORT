'use client';
/**
 * AuthGate — client-side route protection.
 *
 * TWO MODES:
 *
 * <AuthGate>
 *   Hard gate. User must be authenticated to see ANY content.
 *   While Privy initialises  → spinner (prevents flash of protected content)
 *   Not authenticated        → redirects to /login?from=<current path>
 *   Authenticated            → renders children
 *
 * <AuthGate softGate>
 *   Soft gate. Content is visible to everyone (good for feed, signals).
 *   Protected ACTIONS use useAuthGuard() / AuthRequiredModal inline.
 *   Always renders children immediately.
 *
 * WHY BOTH:
 *   Hard gate is for pages like /trade /wallet /profile where even
 *   seeing the shell leaks user data.
 *   Soft gate is for pages like the feed where public browsing is fine
 *   but placing a trade requires login.
 */
import { useEffect } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { useAuth } from '@/hooks/useAuth';
import { useTelegram } from '@/hooks/useTelegram';

export default function AuthGate({ children, softGate = false }) {
  const { ready: privyReady, isAuthed, login } = useAuth();
  const { user: tgUser, ready: tgReady }       = useTelegram();
  const router   = useRouter();
  const pathname = usePathname();

  const isReady  = privyReady && tgReady;
  const loggedIn = isAuthed || !!tgUser;

  // Hard gate: redirect to /login once we know the user is NOT logged in.
  // We wait for isReady so we don't redirect during Privy initialisation.
  useEffect(() => {
    if (!softGate && isReady && !loggedIn) {
      router.replace(`/login?from=${encodeURIComponent(pathname)}`);
    }
  }, [softGate, isReady, loggedIn, router, pathname]);

  // ── Soft gate: always render — protected actions handled inline ──────────
  if (softGate) return <>{children}</>;

  // ── Hard gate ────────────────────────────────────────────────────────────

  // Still initialising — show branded spinner, never blank/broken page
  if (!isReady) {
    return (
      <div className="auth-screen">
        <div className="auth-logo">NORT</div>
        <div style={{
          fontSize:   11,
          fontFamily: "'DM Mono', monospace",
          color:      'rgba(255,255,255,0.35)',
          marginTop:  12,
          animation:  'pulse 1.5s ease-in-out infinite',
        }}>
          Loading…
        </div>
      </div>
    );
  }

  // Not logged in → blank screen while redirect is in flight
  // (avoids brief flash of protected content before router.replace fires)
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
