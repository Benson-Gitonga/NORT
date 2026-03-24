import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Only apply smart routing to the root path
  if (pathname !== '/') return NextResponse.next();

  // Check for auth cookie set by Privy login
  const authCookie = request.cookies.get('nort_auth');
  const isAuthed = authCookie?.value === 'true';

  // Logged in → serve dashboard (normal Next.js routing)
  if (isAuthed) return NextResponse.next();

  // Logged out → rewrite to /landing-view (internal route, URL stays "/")
  return NextResponse.rewrite(new URL('/landing-view', request.url));
}

export const config = {
  matcher: ['/'],
};
