'use client';
import { useEffect } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { useAuth } from '@/hooks/useAuth';
import { useTelegram } from '@/hooks/useTelegram';

/**
 * AuthGate — two modes:
 *
 * <AuthGate>               → full gate: redirects to /login if not authenticated
 * <AuthGate softGate>      → show content publicly, just block trade actions
 */
export default function AuthGate({ children, softGate = false }) {
  const { ready, isAuthed } = useAuth();
  const { user: tgUser, ready: tgReady } = useTelegram();
  const router = useRouter();
  const pathname = usePathname();

  const isReady  = ready && tgReady;
  const loggedIn = isAuthed || !!tgUser;

  useEffect(() => {
    if (!softGate && isReady && !loggedIn) {
      router.replace(`/login?from=${encodeURIComponent(pathname)}`);
    }
  }, [softGate, isReady, loggedIn, pathname, router]);

  // Still initialising — show brief spinner
  if (!isReady) {
    return (
      <div className="auth-screen">
        <div className="auth-logo">NORT</div>
        <div className="auth-sub">Loading...</div>
      </div>
    );
  }

  // softGate: always show content, no wall
  if (softGate) return children;

  // Hard gate: not logged in → redirect (handled by useEffect above)
  if (!loggedIn) {
    return (
      <div className="auth-screen">
        <div className="auth-logo">NORT</div>
        <div className="auth-sub">Redirecting...</div>
      </div>
    );
  }

  return children;
}
