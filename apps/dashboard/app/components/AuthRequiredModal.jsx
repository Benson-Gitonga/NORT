'use client';
import { useTelegram } from '@/hooks/useTelegram';

/**
 * AuthRequiredModal — shown when an unauthenticated user tries to access
 * a protected route or action. Follows human-centered design:
 *
 * ✅ Explains WHY login is needed (contextual message)
 * ✅ Shows what they'll gain (not just a wall)
 * ✅ Easy to dismiss (overlay click or X button)
 * ✅ Non-blocking — they stay on the current page
 * ✅ Haptic feedback on mobile/Telegram
 */
export default function AuthRequiredModal({ onLogin, onDismiss, message = 'Connect your wallet to continue', title = 'Login Required' }) {
  const { haptic } = useTelegram();

  const handleLogin = () => {
    haptic?.medium?.();
    onLogin?.();
  };

  const handleDismiss = () => {
    haptic?.light?.();
    onDismiss?.();
  };

  return (
    <div
      className="modal-overlay"
      onClick={handleDismiss}
      role="dialog"
      aria-modal="true"
      aria-label={title}
    >
      <div
        className="modal"
        onClick={(e) => e.stopPropagation()}
        style={{ position: 'relative' }}
      >
        {/* Drag handle (mobile bottom sheet feel) */}
        <div className="modal-handle" />

        {/* Close button */}
        <button
          onClick={handleDismiss}
          aria-label="Close"
          style={{
            position:   'absolute',
            top:        12,
            right:      14,
            background: 'none',
            border:     'none',
            color:      'var(--text-muted)',
            fontSize:   18,
            cursor:     'pointer',
            lineHeight: 1,
            padding:    4,
          }}
        >
          ✕
        </button>

        {/* Icon */}
        <div style={{
          width:        48,
          height:       48,
          borderRadius: '50%',
          background:   'var(--teal-dim)',
          border:       '1px solid var(--teal-border)',
          display:      'flex',
          alignItems:   'center',
          justifyContent: 'center',
          margin:       '8px auto 16px',
          fontSize:     22,
        }}>
          🔑
        </div>

        <div className="modal-title">{title}</div>
        <div className="modal-sub" style={{ marginBottom: 8 }}>Wallet connection needed</div>

        <div
          className="modal-q"
          style={{ marginBottom: 24, textAlign: 'center', lineHeight: 1.5 }}
        >
          {message}
        </div>

        {/* Benefits nudge */}
        <div style={{
          background:   'var(--glass-bg)',
          border:       '1px solid var(--glass-border)',
          borderRadius: 10,
          padding:      '12px 14px',
          marginBottom: 20,
          display:      'flex',
          flexDirection:'column',
          gap:          7,
          fontSize:     12,
          color:        'var(--text-secondary)',
          fontFamily:   'DM Mono, monospace',
        }}>
          <div>✦ $1,000 paper USDC to start</div>
          <div>✦ AI-powered trade signals</div>
          <div>✦ Leaderboard & achievements</div>
          <div>✦ Paper trades only · No real funds</div>
        </div>

        <button
          className="modal-cta"
          onClick={handleLogin}
          style={{ width: '100%' }}
        >
          Connect Wallet / Sign In
        </button>

        <button
          onClick={handleDismiss}
          style={{
            width:      '100%',
            marginTop:  10,
            background: 'none',
            border:     'none',
            color:      'var(--text-muted)',
            fontSize:   12,
            cursor:     'pointer',
            padding:    '8px 0',
            fontFamily: 'DM Mono, monospace',
          }}
        >
          Maybe later
        </button>
      </div>
    </div>
  );
}
