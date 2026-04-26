'use client';
/**
 * useAuthGuard / useRequireAuth
 *
 * Intercepts navigation or actions for unauthenticated users.
 * Shows AuthRequiredModal inline instead of a hard redirect.
 *
 * Usage (navigation guard — e.g. in Navbar):
 *   const { guardedNavigate, pendingRoute, pendingMessage, handleLogin, dismiss } = useAuthGuard();
 *   <button onClick={() => guardedNavigate('/trade', 'See your open bets')}>Bets</button>
 *   {pendingRoute && <AuthRequiredModal message={pendingMessage} onLogin={handleLogin} onDismiss={dismiss} />}
 *
 * Usage (action guard — e.g. trade button on a soft-gated page):
 *   const { requireAuth, AuthModal } = useRequireAuth();
 *   // Render <>{AuthModal}</> once in your JSX
 *   // Call requireAuth({ action: 'trade', onSuccess: openTradeModal }) on button click
 */
import { useState, useCallback } from 'react';
import { useAuth } from './useAuth';
import { useTelegram } from './useTelegram';
import { useRouter } from 'next/navigation';
import AuthRequiredModal from '@/components/AuthRequiredModal';

// ─── useAuthGuard — for guarded navigation (used in Navbar) ──────────────────
export function useAuthGuard() {
  const { isAuthed, login } = useAuth();
  const { user: tgUser }    = useTelegram();
  const loggedIn            = isAuthed || !!tgUser;
  const router              = useRouter();

  const [pendingRoute,   setPendingRoute]   = useState(null);
  const [pendingMessage, setPendingMessage] = useState('Connect your wallet to continue');

  const guardedNavigate = useCallback((href, message) => {
    if (loggedIn) {
      router.push(href);
    } else {
      setPendingRoute(href);
      if (message) setPendingMessage(message);
    }
  }, [loggedIn, router]);

  const handleLogin = useCallback(() => {
    login();
    setPendingRoute(null);
  }, [login]);

  const dismiss = useCallback(() => setPendingRoute(null), []);

  const navigateAfterLogin = useCallback((fallback = '/') => {
    router.push(pendingRoute || fallback);
    setPendingRoute(null);
  }, [pendingRoute, router]);

  return { pendingRoute, pendingMessage, guardedNavigate, handleLogin, dismiss, navigateAfterLogin };
}

// ─── useRequireAuth — for guarded actions on soft-gated pages ─────────────────
export function useRequireAuth() {
  const { isAuthed, login } = useAuth();
  const { user: tgUser }    = useTelegram();
  const loggedIn            = isAuthed || !!tgUser;

  const [promptConfig, setPromptConfig] = useState(null); // null = closed

  /**
   * Call before any protected action.
   * If logged in  → calls onSuccess() immediately
   * If not        → opens AuthRequiredModal
   *
   * @param {{ action?: string, message?: string, onSuccess?: () => void }} opts
   */
  const requireAuth = useCallback((opts = {}) => {
    const { action = 'continue', message, onSuccess } = opts;
    if (loggedIn) {
      onSuccess?.();
    } else {
      setPromptConfig({ action, message, onSuccess });
    }
  }, [loggedIn]);

  const closePrompt = useCallback(() => setPromptConfig(null), []);

  const handleModalLogin = useCallback(() => {
    login();
    setPromptConfig(null);
  }, [login]);

  // AuthModal — render this once in the component that uses this hook
  const AuthModal = promptConfig ? (
    <AuthRequiredModal
      title={`Sign in to ${promptConfig.action}`}
      message={
        promptConfig.message ||
        'Connect your wallet to access this feature.'
      }
      onLogin={handleModalLogin}
      onDismiss={closePrompt}
    />
  ) : null;

  return { requireAuth, AuthModal, isAuthed: loggedIn };
}

export default useAuthGuard;
