'use client';
import { useState, useCallback } from 'react';
import { useAuth } from './useAuth';
import { useRouter } from 'next/navigation';

/**
 * useAuthGuard — intercepts navigation to protected routes when unauthenticated.
 *
 * Usage:
 *   const { pendingRoute, guardedNavigate, handleLogin, dismiss } = useAuthGuard();
 *
 *   // In JSX, replace <Link href="/trade"> with:
 *   <button onClick={() => guardedNavigate('/trade', 'Place and track your bets')}>Trade</button>
 *
 *   // Then render the modal:
 *   {pendingRoute && (
 *     <AuthRequiredModal
 *       message={pendingMessage}
 *       onLogin={handleLogin}
 *       onDismiss={dismiss}
 *     />
 *   )}
 */
export function useAuthGuard() {
  const { isAuthed, login } = useAuth();
  const router = useRouter();
  const [pendingRoute, setPendingRoute] = useState(null);
  const [pendingMessage, setPendingMessage] = useState('Connect your wallet to continue');

  const guardedNavigate = useCallback((href, message) => {
    if (isAuthed) {
      router.push(href);
    } else {
      setPendingRoute(href);
      if (message) setPendingMessage(message);
    }
  }, [isAuthed, router]);

  const handleLogin = useCallback(() => {
    login();
    setPendingRoute(null);
  }, [login]);

  const dismiss = useCallback(() => {
    setPendingRoute(null);
  }, []);

  // After login succeeds (called externally if needed)
  const navigateAfterLogin = useCallback((fallback = '/') => {
    router.push(pendingRoute || fallback);
    setPendingRoute(null);
  }, [pendingRoute, router]);

  return {
    pendingRoute,
    pendingMessage,
    guardedNavigate,
    handleLogin,
    dismiss,
    navigateAfterLogin,
  };
}
