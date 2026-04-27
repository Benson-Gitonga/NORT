'use client';
/**
 * TokenStore — singleton that holds the Privy getAccessToken function.
 *
 * Problem being solved:
 *   Privy's React SDK does NOT export getAccessToken as a standalone function.
 *   It only exists as a method on the object returned by usePrivy().
 *   lib/api.js runs outside of React (no hooks), so it cannot call usePrivy().
 *   The old code did `import { getAccessToken } from '@privy-io/react-auth'`
 *   which resolves to undefined — causing every authFetch to send no token.
 *
 * Solution:
 *   PrivyProvidersInner calls TokenStore.set(getAccessToken) once on mount.
 *   lib/api.js calls TokenStore.get()() to retrieve a fresh token anywhere.
 *
 * This is the standard pattern recommended by Privy for non-hook contexts.
 */

let _getAccessToken = null;

export const TokenStore = {
  set(fn) {
    _getAccessToken = fn;
  },
  get() {
    return _getAccessToken;
  },
};
