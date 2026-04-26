'use client';
import { useAuth } from '@/hooks/useAuth';
import { useTelegram } from '@/hooks/useTelegram';

/**
 * AuthGate — two modes:
 *
 * <AuthGate>               → full gate: must be logged in to see content
 * <AuthGate softGate>      → show content publicly, just block trade actions
 */
export default function AuthGate({ children, softGate = false }) {
  const { ready, isAuthed, login } = useAuth();
  const { user: tgUser, ready: tgReady } = useTelegram();

  const isReady  = ready && tgReady;
  const loggedIn = isAuthed || !!tgUser;

  // Still initialising — show brief spinner
  if (!isReady) {
    return (
      <div className="auth-screen">
        <div className="auth-logo">NORT</div>
      </div>
    );
  }

  // softGate: always show content, no wall
  if (softGate) return children;

  // Hard gate: not logged in → login screen
  if (!loggedIn) {
    return (
      <div className="auth-screen">
        <div className="auth-logo">NORT</div>
        <button className="auth-btn outline" onClick={login} style={{ marginTop: 32 }}>
          Connect Wallet
        </button>
        <div style={{ fontSize: 10, fontFamily: "'DM Mono', monospace", color: '#fff', textAlign: 'center', lineHeight: 1.6, opacity: 0.5 }}>
          Paper trades only · No real funds at risk
        </div>
      </div>
    );
  }

  return children;
}
