'use client';
import { useState } from 'react';
import { useTradingMode } from './TradingModeContext';

export default function ModeToggleModal({ onClose }) {
  const { mode, setMode } = useTradingMode();
  const [phase, setPhase] = useState('warning');  // 'warning' | 'loading' | 'error'
  const [errorMsg, setErrorMsg] = useState('');

  const isGoingReal = mode === 'paper';

  // ── Switching real → paper (instant, no warning needed) ──────────────────
  async function switchToPaper() {
    setPhase('loading');
    try {
      await setMode('paper', false);
      onClose();
    } catch {
      setErrorMsg('Failed to switch. Try again.');
      setPhase('error');
    }
  }

  // ── Switching paper → real (just confirmation, no gates) ─────────────────
  async function switchToReal() {
    setPhase('loading');
    try {
      await setMode('real', true);
      onClose();
    } catch (err) {
      setErrorMsg(err?.detail?.message || err?.detail || 'Switch failed.');
      setPhase('error');
    }
  }

  return (
    <div className="modal-overlay" style={{ zIndex: 9999 }} onClick={onClose}>
      <div
        className="modal"
        onClick={e => e.stopPropagation()}
        style={{
          maxWidth: 400,
          border: `1.5px solid ${isGoingReal ? '#F59E0B' : 'var(--border)'}`,
        }}
      >
        <div className="modal-handle" />

        {/* ── paper → real warning ───────────────────────────────────────── */}
        {isGoingReal && phase === 'warning' && (
          <>
            <div className="modal-title" style={{ color: '#F59E0B' }}>
              ⚠ Real Trading Mode
            </div>
            <div className="modal-sub" style={{ marginTop: 10, lineHeight: 1.7 }}>
              You are about to switch to <strong style={{ color: 'var(--white)' }}>real trading mode</strong>.
            </div>
            <div style={{
              margin: '14px 0',
              padding: '12px 14px',
              background: 'rgba(245,158,11,0.08)',
              border: '1px solid rgba(245,158,11,0.25)',
              borderRadius: 10,
              fontSize: 13,
              lineHeight: 1.7,
              color: 'var(--muted)',
            }}>
              • Trades will use <strong style={{ color: '#F59E0B' }}>real USDC</strong> on Base<br />
              • You can lose money<br />
              • Paper trading is available at any time<br />
              • Switch back to paper instantly from the nav bar
            </div>
            <button
              className="modal-cta"
              onClick={switchToReal}
              style={{ background: '#F59E0B', color: '#000', fontWeight: 700 }}
            >
              I understand — Enable Real Trading
            </button>
            <button
              className="chip-btn"
              onClick={onClose}
              style={{ width: '100%', marginTop: 8, opacity: 0.6 }}
            >
              Cancel — Stay on Paper
            </button>
          </>
        )}

        {/* ── real → paper (instant, just confirm) ──────────────────────── */}
        {!isGoingReal && phase === 'warning' && (
          <>
            <div className="modal-title">Switch to Paper Mode</div>
            <div className="modal-sub" style={{ marginTop: 8, lineHeight: 1.6 }}>
              Switching to paper trading. No real money will be used.
              Your open real positions are not affected.
            </div>
            <button className="modal-cta" onClick={switchToPaper} style={{ marginTop: 20 }}>
              Switch to Paper Mode
            </button>
            <button
              className="chip-btn"
              onClick={onClose}
              style={{ width: '100%', marginTop: 8, opacity: 0.6 }}
            >
              Cancel
            </button>
          </>
        )}

        {/* ── Loading ────────────────────────────────────────────────────── */}
        {phase === 'loading' && (
          <div style={{ textAlign: 'center', padding: '32px 0', color: 'var(--muted)' }}>
            Switching mode...
          </div>
        )}

        {/* ── Error ──────────────────────────────────────────────────────── */}
        {phase === 'error' && (
          <>
            <div className="modal-title" style={{ color: '#EF4444' }}>Switch Failed</div>
            <div style={{ marginTop: 8, color: 'var(--muted)', fontSize: 13 }}>
              {errorMsg}
            </div>
            <button
              className="modal-cta"
              onClick={() => { setPhase('warning'); setErrorMsg(''); }}
              style={{ marginTop: 16 }}
            >
              Try Again
            </button>
          </>
        )}
      </div>
    </div>
  );
}
