import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export default function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const authToken = request.cookies.get('privy-token');

  // Redirect unauthenticated users on root to landing page
  if (pathname === '/') {
    if (!authToken) {
      return NextResponse.rewrite(new URL('https://nort-landing-nine.vercel.app', request.url));
    }
  }
  // Allow access to /login and /dashboard for all, but redirect if unauth on others except public endpoints
  const publicPaths = ['/', '/login'];
  if (!authToken && !publicPaths.includes(pathname)) {
    return NextResponse.redirect(new URL('/', request.url));
  }
  return NextResponse.next();
}

export const config = {
  matcher: [
    '/((?!_next/static|_next/image|favicon.ico|$).*)',
  ],
};