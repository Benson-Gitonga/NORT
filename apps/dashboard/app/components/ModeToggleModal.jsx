'use client';
import { useState } from 'react';
import { useTradingMode } from './TradingModeContext';

const CONFIRM_PHRASE = 'I understand this uses real money';

export default function ModeToggleModal({ onClose }) {
  const { mode, gates, canSwitchToReal, setMode } = useTradingMode();
  const [phase, setPhase] = useState('info');   // 'info' | 'confirm' | 'loading' | 'error'
  const [typed, setTyped] = useState('');
  const [errorMsg, setErrorMsg] = useState('');

  const isGoingReal = mode === 'paper';

  // ── Switching real → paper (instant, no gates) ───────────────────────────
  async function switchToPaper() {
    setPhase('loading');
    try {
      await setMode('paper', false);
      onClose();
    } catch (e) {
      setErrorMsg('Failed to switch. Try again.');
      setPhase('error');
    }
  }

  // ── Switching paper → real (all gates + typed confirmation) ──────────────
  async function switchToReal() {
    if (typed.trim().toLowerCase() !== CONFIRM_PHRASE.toLowerCase()) return;
    setPhase('loading');
    try {
      await setMode('real', true);
      onClose();
    } catch (err) {
      const errors = err?.detail?.errors || [err?.detail || 'Switch failed.'];
      setErrorMsg(errors.join(' '));
      setPhase('error');
    }
  }

  return (
    <div className="modal-overlay" style={{ zIndex: 9999 }} onClick={onClose}>
      <div
        className="modal"
        onClick={e => e.stopPropagation()}
        style={{ maxWidth: 420, border: isGoingReal ? '1.5px solid #F59E0B' : '1.5px solid var(--border)' }}
      >
        <div className="modal-handle" />

        {/* ── Switching to paper (simple confirm) ────────────────────────── */}
        {!isGoingReal && phase !== 'loading' && (
          <>
            <div className="modal-title">Switch to Paper Mode</div>
            <div className="modal-sub" style={{ marginTop: 8 }}>
              Your real trading will be paused. All new trades will be simulated.
              Your open real positions are not affected.
            </div>
            <button className="modal-cta" onClick={switchToPaper} style={{ marginTop: 20 }}>
              Switch to Paper Mode
            </button>
            <button className="chip-btn" onClick={onClose} style={{ width: '100%', marginTop: 8, opacity: 0.6 }}>
              Cancel
            </button>
          </>
        )}

        {/* ── Switching to real — info phase ─────────────────────────────── */}
        {isGoingReal && phase === 'info' && (
          <>
            <div className="modal-title" style={{ color: '#F59E0B' }}>⚠ Enable Real Trading</div>
            <div className="modal-sub" style={{ marginTop: 8, lineHeight: 1.6 }}>
              Real trading uses <strong>actual USDC</strong> on Base. You can lose money.
              Paper trading mode will remain available at any time.
            </div>

            {/* Gate status */}
            <div style={{ marginTop: 16, display: 'flex', flexDirection: 'column', gap: 8 }}>
              <GateRow
                label="KYC verified"
                passed={gates.kyc_approved}
                failNote="Identity verification required"
              />
              <GateRow
                label={`Min. balance ($${gates.min_balance_usdc ?? 10} USDC)`}
                passed={gates.min_balance_met}
                failNote={`Have $${gates.current_balance ?? 0} — need $${gates.min_balance_usdc ?? 10}`}
              />
              <GateRow
                label="Explicit confirmation"
                passed={false}
                failNote="Required below"
              />
            </div>

            {canSwitchToReal ? (
              <button
                className="modal-cta"
                onClick={() => setPhase('confirm')}
                style={{ marginTop: 20, background: '#F59E0B', color: '#000' }}
              >
                Continue to Confirmation →
              </button>
            ) : (
              <div style={{
                marginTop: 16, padding: '10px 14px',
                background: 'rgba(239,68,68,0.1)', borderRadius: 8,
                color: '#EF4444', fontSize: 13, lineHeight: 1.5,
              }}>
                Complete the gates above before enabling real trading.
              </div>
            )}

            <button className="chip-btn" onClick={onClose} style={{ width: '100%', marginTop: 8, opacity: 0.6 }}>
              Cancel
            </button>
          </>
        )}

        {/* ── Switching to real — typed confirmation phase ────────────────── */}
        {isGoingReal && phase === 'confirm' && (
          <>
            <div className="modal-title" style={{ color: '#F59E0B' }}>Final Confirmation</div>
            <div className="modal-sub" style={{ marginTop: 8 }}>
              Type exactly: <strong style={{ color: 'var(--white)' }}>{CONFIRM_PHRASE}</strong>
            </div>
            <div className="modal-input-wrap" style={{ marginTop: 16 }}>
              <input
                className="modal-input"
                type="text"
                placeholder={CONFIRM_PHRASE}
                value={typed}
                onChange={e => setTyped(e.target.value)}
                autoFocus
                style={{ borderColor: typed.trim().toLowerCase() === CONFIRM_PHRASE.toLowerCase() ? '#10B981' : undefined }}
              />
            </div>
            <button
              className="modal-cta"
              onClick={switchToReal}
              disabled={typed.trim().toLowerCase() !== CONFIRM_PHRASE.toLowerCase()}
              style={{ marginTop: 12, background: '#F59E0B', color: '#000' }}
            >
              Enable Real Trading
            </button>
            <button className="chip-btn" onClick={() => setPhase('info')} style={{ width: '100%', marginTop: 8, opacity: 0.6 }}>
              ← Back
            </button>
          </>
        )}

        {/* ── Loading ─────────────────────────────────────────────────────── */}
        {phase === 'loading' && (
          <div style={{ textAlign: 'center', padding: '24px 0', color: 'var(--muted)' }}>
            Switching mode...
          </div>
        )}

        {/* ── Error ───────────────────────────────────────────────────────── */}
        {phase === 'error' && (
          <>
            <div className="modal-title" style={{ color: '#EF4444' }}>Switch Failed</div>
            <div style={{ marginTop: 8, color: 'var(--muted)', fontSize: 13, lineHeight: 1.6 }}>
              {errorMsg}
            </div>
            <button className="modal-cta" onClick={() => { setPhase('info'); setErrorMsg(''); }} style={{ marginTop: 16 }}>
              Try Again
            </button>
          </>
        )}
      </div>
    </div>
  );
}

function GateRow({ label, passed, failNote }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 13 }}>
      <span style={{
        width: 20, height: 20, borderRadius: '50%', flexShrink: 0,
        background: passed ? '#10B981' : '#EF4444',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 11, color: '#fff',
      }}>
        {passed ? '✓' : '✗'}
      </span>
      <span style={{ color: passed ? 'var(--white)' : 'var(--muted)' }}>
        {label}
        {!passed && <span style={{ color: '#EF4444', marginLeft: 6 }}>— {failNote}</span>}
      </span>
    </div>
  );
}
