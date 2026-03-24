import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export function middleware(request: NextRequest) {
  const url = request.nextUrl.clone();
  
  // 1. Check if the user is hitting the root page
  if (url.pathname === '/') {
    
    // 2. Check for your auth cookie (change 'session' to your actual cookie name)
    const session = request.cookies.get('session'); 

    // 3. If NO session exists, show the landing page
    if (!session) {
      return NextResponse.rewrite(new URL('https://nort-landing-nine.vercel.app', request.url));
    }
  }

  // Otherwise, let them see the Dashboard as normal
  return NextResponse.next();
}

// Ensure this only runs on the homepage to save performance
export const config = {
  matcher: '/',
};