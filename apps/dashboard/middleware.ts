// middleware.ts in your Main NORT Repo
import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

    // Allow all users to access the main page; AuthGate handles login/signup gating
    return NextResponse.next();

  return NextResponse.next();
}

// 3. The Matcher is critical. It must include '/' but exclude static files.
export const config = {
  matcher: [
    /*
     * Match all request paths except for the ones starting with:
     * - api (API routes)
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     * This allows '/' to be caught and processed.
     */
    '/' ,
  ],
};