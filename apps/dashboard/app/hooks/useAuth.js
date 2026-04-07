"use client";
import { useRealAuth } from "./useRealAuth";
import { useMockAuth } from "./useMockAuth";

/**
 * useAuth — selects the correct auth implementation.
 *
 * IMPORTANT: Mock auth is intentionally blocked in production builds.
 * Even if NEXT_PUBLIC_USE_MOCK_AUTH is set, it will be ignored unless
 * NODE_ENV is 'development'. This prevents accidental production bypass.
 */
export function useAuth() {
  const isMock =
    process.env.NEXT_PUBLIC_USE_MOCK_AUTH === "true" &&
    process.env.NODE_ENV !== "production";

  // Rules of Hooks: we must call both hooks unconditionally, then select.
  // Both hooks are lightweight and this satisfies React's hook ordering rules.
  const realAuth = useRealAuth();
  const mockAuth = useMockAuth();

  return isMock ? mockAuth : realAuth;
}
