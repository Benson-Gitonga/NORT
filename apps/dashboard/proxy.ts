import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

/**
 * proxy.ts — NORT route protection & entry point control.
 *
 * Turbopack uses proxy.ts as its middleware file.
 * middleware.ts has been removed — do NOT recreate it alongside this file.
 *
 * Flow:
 *  GET /                    → unauthenticated: rewrite to external landing page
 *                             authenticated:   serve dashboard feed (page.jsx)
 *  GET /login               → always public; if already authed: redirect to ?from or /
 *  GET /signals
 *  GET /markets
 *  GET /leaderboard         → fully public, no auth needed
 *  GET /trade
 *  GET /wallet
 *  GET /profile
 *  GET /achievements
 *  GET /market/:id
 *  GET /overview            → protected; unauthenticated → /login?from=<path>
 *  GET /<anything else>     → pass through (static assets handled by matcher)
 */

// ── Auth helper ───────────────────────────────────────────────────────────────
// Privy sets 'privy-token' as an httpOnly cookie after login.
// A real Privy JWT has 3 dot-separated base64url segments and is >20 chars.
// This is a format check only — full verification happens server-side in FastAPI.
function checkAuth(request: NextRequest): boolean {
  const token = request.cookies.get('privy-token')?.value ?? '';
  return token.length > 20 && token.split('.').length === 3;
}

// ── Fully public path prefixes (no auth required) ────────────────────────────
const PUBLIC_PREFIXES = ['/signals', '/markets', '/leaderboard'];

// ── Protected path prefixes (auth required) ───────────────────────────────────
const PROTECTED_PREFIXES = [
  '/trade',
  '/wallet',
  '/profile',
  '/achievements',
  '/market',
  '/overview',
];

function isPublic(pathname: string): boolean {
  return PUBLIC_PREFIXES.some(p => pathname === p || pathname.startsWith(p + '/'));
}

function isProtected(pathname: string): boolean {
  return PROTECTED_PREFIXES.some(p => pathname === p || pathname.startsWith(p + '/'));
}

// ── Middleware ────────────────────────────────────────────────────────────────
export default function proxy(request: NextRequest) {
  const { pathname, searchParams } = request.nextUrl;
  const isAuthenticated = checkAuth(request);

  // 1. Root: unauthenticated → rewrite to external landing page (URL stays as /)
  //          authenticated   → serve the Next.js feed
  if (pathname === '/') {
    if (!isAuthenticated) {
      return NextResponse.rewrite(
        new URL('https://nort-landing-nine.vercel.app', request.url)
      );
    }
    return NextResponse.next();
  }

  // 2. /login: always public
  //    If already authenticated, bounce back to ?from or / to avoid stale login page
  if (pathname === '/login') {
    if (isAuthenticated) {
      const from = searchParams.get('from') ?? '/';
      // Open-redirect guard: only allow same-origin internal paths
      const safePath = from.startsWith('/') && !from.startsWith('//') ? from : '/';
      return NextResponse.redirect(new URL(safePath, request.url));
    }
    return NextResponse.next();
  }

  // 3. Fully public paths — pass through unconditionally
  if (isPublic(pathname)) {
    return NextResponse.next();
  }

  // 4. Protected paths — redirect unauthenticated users to /login with return path
  if (isProtected(pathname) && !isAuthenticated) {
    const loginUrl = new URL('/login', request.url);
    loginUrl.searchParams.set('from', pathname);
    return NextResponse.redirect(loginUrl);
  }

  // 5. Everything else — pass through
  return NextResponse.next();
}

export const config = {
  // Run on all routes except Next.js internals and static file extensions
  matcher: [
    '/((?!_next/static|_next/image|favicon\\.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico|woff2?|ttf|eot)$).*)',
  ],
};
