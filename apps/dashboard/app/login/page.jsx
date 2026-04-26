'use client';
/**
 * /login — Wallet connect entry point.
 *
 * IMPORTANT: useSearchParams() requires a Suspense boundary in Next.js App Router.
 * Without it the build throws:
 *   "useSearchParams() should be wrapped in a suspense boundary"
 * We split into LoginPageInner (reads params) + a Suspense wrapper as the export.
 *
 * Behaviour:
 *   1. Already authenticated → redirect to ?from= path or /
 *   2. Not authenticated → auto-open Privy modal after 300ms
 *   3. After successful login → redirect to ?from= path or /
 *   4. User can click the button if they dismissed the modal
 */
import { Suspense, useEffect, useRef } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useAuth } from '@/hooks/useAuth';

// ─── Inner component (safe to use useSearchParams here inside Suspense) ──────
function LoginPageInner() {
  const { ready, isAuthed, login } = useAuth();
  const router       = useRouter();
  const searchParams = useSearchParams();
  const from         = searchParams?.get('from') || '/';
  const didAutoOpen  = useRef(false);

  // If already authenticated, go straight to destination
  useEffect(() => {
    if (ready && isAuthed) {
      router.replace(from);
    }
  }, [ready, isAuthed, from, router]);

  // Auto-open Privy modal once, 300ms after mount
  useEffect(() => {
    if (!ready || isAuthed || didAutoOpen.current) return;
    didAutoOpen.current = true;
    const t = setTimeout(() => login(), 300);
    return () => clearTimeout(t);
  }, [ready, isAuthed, login]);

  // Human-readable destination name shown in the sub-copy
  const DEST_LABELS: Record<string, string> = {
    '/trade':        'My Bets',
    '/wallet':       'Wallet',
    '/profile':      'Profile',
    '/achievements': 'Achievements',
    '/signals':      'Signals',
    '/market':       'Market',
    '/overview':     'Overview',
  };
  const destKey = Object.keys(DEST_LABELS).find(k => from.startsWith(k));
  const destLabel = destKey ? DEST_LABELS[destKey] : null;

  return (
    <div className="auth-screen">
      {/* Logo */}
      <div className="auth-logo">NORT</div>

      {/* Context-aware sub-copy */}
      {destLabel ? (
        <div className="auth-sub" style={{ maxWidth: 280, lineHeight: 1.6 }}>
          Connect your wallet to access&nbsp;
          <strong style={{ color: 'var(--teal, #00f2ff)' }}>{destLabel}</strong>.
        </div>
      ) : (
        <div className="auth-sub" style={{ maxWidth: 280, lineHeight: 1.6 }}>
          AI-powered prediction market signals.<br />
          Connect your wallet to start trading.
        </div>
      )}

      {/* Feature bullets */}
      <div style={{
        display:       'flex',
        flexDirection: 'column',
        gap:           8,
        margin:        '20px 0',
        padding:       '16px 20px',
        background:    'var(--glass-bg, rgba(255,255,255,0.04))',
        border:        '1px solid var(--glass-border, rgba(255,255,255,0.08))',
        borderRadius:  12,
        width:         '100%',
        maxWidth:      280,
        textAlign:     'left',
        fontSize:      12,
        fontFamily:    "'DM Mono', monospace",
        color:         'var(--text-secondary, rgba(255,255,255,0.6))',
      }}>
        <div>✦ $1,000 paper USDC to start</div>
        <div>✦ AI-powered trade signals</div>
        <div>✦ Leaderboard &amp; achievements</div>
        <div>✦ Real wallet, zero real risk</div>
      </div>

      {/* Manual CTA — shown if Privy modal was dismissed */}
      {ready && !isAuthed && (
        <button
          className="auth-btn outline"
          onClick={login}
          style={{ width: '100%', maxWidth: 280 }}
        >
          Connect Wallet / Sign In
        </button>
      )}

      {/* Loading state while Privy initialises */}
      {!ready && (
        <div style={{
          fontSize:   12,
          fontFamily: "'DM Mono', monospace",
          color:      'rgba(255,255,255,0.4)',
          marginTop:  12,
        }}>
          Loading…
        </div>
      )}

      {/* Back to landing */}
      <a
        href="https://nort-landing-nine.vercel.app"
        style={{
          marginTop:      20,
          fontSize:       11,
          fontFamily:     "'DM Mono', monospace",
          color:          'rgba(255,255,255,0.4)',
          textDecoration: 'none',
        }}
      >
        ← Back to home
      </a>

      {/* Disclaimer */}
      <div style={{
        marginTop:  16,
        fontSize:   10,
        fontFamily: "'DM Mono', monospace",
        color:      'rgba(255,255,255,0.3)',
        textAlign:  'center',
        lineHeight: 1.6,
        maxWidth:   260,
      }}>
        Paper trades only · No real funds at risk<br />
        Powered by Privy · Base network
      </div>
    </div>
  );
}

// ─── Exported page — MUST wrap in Suspense for useSearchParams ────────────────
export default function LoginPage() {
  return (
    <Suspense fallback={
      <div className="auth-screen">
        <div className="auth-logo">NORT</div>
      </div>
    }>
      <LoginPageInner />
    </Suspense>
  );
}
