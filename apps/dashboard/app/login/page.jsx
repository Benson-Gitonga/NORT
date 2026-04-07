'use client';
import { useEffect, useRef } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useAuth } from '@/hooks/useAuth';

/**
 * /login — Entry point for wallet connection.
 *
 * Behaviour:
 * 1. If already authenticated → redirect to 'from' param or '/'
 * 2. If not authenticated → auto-open Privy wallet modal
 * 3. After successful login → redirect to 'from' param or '/'
 * 4. User can also manually click the button if modal was dismissed
 *
 * The middleware sends unauthenticated users here (with ?from=<intended path>)
 * instead of directly to the landing page, so the auth flow is clear.
 */
export default function LoginPage() {
  const { ready, isAuthed, login } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const from = searchParams?.get('from') || '/';
  const didAutoOpen = useRef(false);

  // Redirect if already logged in
  useEffect(() => {
    if (ready && isAuthed) {
      router.replace(from);
    }
  }, [ready, isAuthed, from, router]);

  // Auto-open Privy modal once Privy is ready and user is not authed
  useEffect(() => {
    if (!ready || isAuthed || didAutoOpen.current) return;
    didAutoOpen.current = true;
    // Small delay so the page renders before the modal pops
    const t = setTimeout(() => { login(); }, 300);
    return () => clearTimeout(t);
  }, [ready, isAuthed, login]);

  // After login, redirect back
  useEffect(() => {
    if (ready && isAuthed) {
      router.replace(from);
    }
  }, [isAuthed, ready, from, router]);

  return (
    <div className="auth-screen">
      {/* Logo */}
      <div className="auth-logo">NORT</div>

      {/* Tagline */}
      <div className="auth-sub" style={{ maxWidth: 280, lineHeight: 1.6 }}>
        AI-powered prediction market signals.<br />
        Connect your wallet to start trading.
      </div>

      {/* Feature bullets */}
      <div style={{
        display:       'flex',
        flexDirection: 'column',
        gap:           8,
        margin:        '24px 0',
        padding:       '16px 20px',
        background:    'var(--glass-bg)',
        border:        '1px solid var(--glass-border)',
        borderRadius:  12,
        width:         '100%',
        maxWidth:      280,
        textAlign:     'left',
        fontSize:      12,
        fontFamily:    "'DM Mono', monospace",
        color:         'var(--text-secondary)',
      }}>
        <div>✦ $1,000 paper USDC to start</div>
        <div>✦ AI-powered trade signals</div>
        <div>✦ Leaderboard & achievements</div>
        <div>✦ Real wallet, zero real risk</div>
      </div>

      {/* CTA — in case the Privy modal was dismissed */}
      {ready && !isAuthed && (
        <button
          className="auth-btn outline"
          onClick={login}
          style={{ width: '100%', maxWidth: 280 }}
        >
          Connect Wallet / Sign In
        </button>
      )}

      {/* Back to landing */}
      <a
        href="https://nort-landing-nine.vercel.app"
        style={{
          marginTop:  16,
          fontSize:   11,
          fontFamily: "'DM Mono', monospace",
          color:      'var(--text-muted)',
          textDecoration: 'none',
          opacity:    0.7,
        }}
      >
        ← Back to home
      </a>

      {/* Disclaimer */}
      <div style={{
        marginTop:  20,
        fontSize:   10,
        fontFamily: "'DM Mono', monospace",
        color:      'var(--text-muted)',
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
