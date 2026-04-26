# Production Reversion & Cleaning Guide

This document tracks temporary changes made to the codebase for local development and debugging. Revert these before deploying to production.

## 1. Proxy Redirect (Bypass Landing Page)
**File**: `apps/dashboard/proxy.ts`

**Current Change**:
```typescript
  // ── Root: unauthenticated → local login (dev) or external landing (prod) ──
  if (pathname === '/') {
    if (!isAuthenticated) {
      if (process.env.NODE_ENV === 'development') {
        return NextResponse.redirect(new URL('/login', request.url));
      }
      return NextResponse.rewrite(
        new URL('https://nort-landing-nine.vercel.app', request.url)
      );
    }
    return NextResponse.next();
  }
```

**Original (OG) Code to Revert to**:
```typescript
  // ── Root: unauthenticated → external landing; authenticated → dashboard ──
  if (pathname === '/') {
    if (!isAuthenticated) {
      return NextResponse.rewrite(
        new URL('https://nort-landing-nine.vercel.app', request.url)
      );
    }
    return NextResponse.next();
  }
```

## 2. Mock Authentication (If Enabled)
**File**: `.env.local`
- Ensure `NEXT_PUBLIC_USE_MOCK_AUTH=false` for production.

---
*Created by Antigravity on 2026-04-08*
