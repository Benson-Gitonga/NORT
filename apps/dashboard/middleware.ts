import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const authToken = request.cookies.get('privy-token');

  // Redirect unauthenticated users on root to landing page
  if (pathname === '/') {
    if (!authToken) {
      return NextResponse.rewrite(new URL('https://nort-landing-nine.vercel.app', request.url));
    }
  }
  // Allow access to /login and /dashboard for all
  return NextResponse.next();
}

export const config = {
  matcher: ['/', '/login', '/dashboard/:path*'],
};