import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

/**
 * NORT proxy.ts — route protection & entry point control.
 *
 * Turbopack uses proxy.ts (not middleware.ts) as its middleware file.
 * DO NOT create middleware.ts alongside this file — they conflict.
 *
 * Flow:
 *  GET /              → unauthenticated: rewrite to external landing page
 *                       authenticated:   serve dashboard feed
 *  GET /login         → always public (Privy wallet modal auto-opens here)
 *                       if already authed: redirect back to ?from or /
 *  GET /signals
 *  GET /leaderboard
 *  GET /markets       → public, no auth needed
 *  GET /<anything>    → unauthenticated: redirect to /login?from=<path>
 *                       authenticated:   serve normally
 */
export default function proxy(request: NextRequest) {
  const { pathname, searchParams } = request.nextUrl;

  // ── Auth cookie check ────────────────────────────────────────────────────
  const privyToken = request.cookies.get('privy-token')?.value ?? '';
  // A real Privy JWT has 3 dot-separated base64url segments and is >20 chars.
  // This is a format check only — full verification happens in FastAPI.
  const isAuthenticated = privyToken.length > 20 && privyToken.split('.').length === 3;

  // ── Root: unauthenticated → external landing; authenticated → dashboard ──
  if (pathname === '/') {
    if (!isAuthenticated) {
      return NextResponse.rewrite(
        new URL('https://nort-landing-nine.vercel.app', request.url)
      );
    }
    return NextResponse.next();
  }

  // ── /login: always public; bounce out if already authed ─────────────────
  if (pathname === '/login') {
    if (isAuthenticated) {
      const from = searchParams.get('from') ?? '/';
      // Prevent open-redirect: only allow same-origin internal paths
      const safePath = from.startsWith('/') && !from.startsWith('//') ? from : '/';
      return NextResponse.redirect(new URL(safePath, request.url));
    }
    return NextResponse.next();
  }

  // ── Fully public paths ───────────────────────────────────────────────────
  const publicPrefixes = ['/signals', '/markets', '/leaderboard'];
  if (publicPrefixes.some(p => pathname === p || pathname.startsWith(p + '/'))) {
    return NextResponse.next();
  }

  // ── Protected: unauthenticated → /login?from=<path> ─────────────────────
  if (!isAuthenticated) {
    const loginUrl = new URL('/login', request.url);
    loginUrl.searchParams.set('from', pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    // Match all paths except Next.js internals and static assets
    '/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico|woff|woff2|ttf|eot)$).*)',
  ],
};
