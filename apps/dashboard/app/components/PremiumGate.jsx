'use client';
/**
 * PremiumGate.jsx
 *
 * Shown when a free user hits their 10/day advice limit OR tries a
 * premium-only feature. Explains free vs premium and gives a clear upgrade path.
 *
 * Props:
 *   open    — boolean
 *   onClose — callback
 *   reason  — 'limit' | 'feature'
 *   used    — how many calls used today (shown in limit mode)
 */

import { useEffect, useState } from 'react';
import { verifyPayment } from '@/lib/api';

const FEATURES = [
  { free: '10 AI advice calls / day',   premium: 'Unlimited AI advice calls'   },
  { free: 'Basic advice only',          premium: 'Full deep-dive analysis'      },
  { free: 'English only',               premium: 'Swahili + English'            },
  { free: 'No conversation memory',     premium: 'AI remembers your context'    },
  { free: 'Standard confidence scores', premium: 'Calibrated to your history'   },
];

export default function PremiumGate({ open, onClose, reason = 'limit', used = 10, limit = 10 }) {
  const [payInput, setPayInput] = useState('');
  const [payLoading, setPayLoading] = useState(false);
  const [payError, setPayError] = useState('');
  const [paySuccess, setPaySuccess] = useState(false);

  useEffect(() => {
    if (!open) return;
    setPayInput('');
    setPayError('');
    setPaySuccess(false);
    const handler = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, onClose]);

  if (!open) return null;

  const handlePay = async () => {
    const proof = payInput.trim();
    if (!proof) return;
    setPayLoading(true);
    setPayError('');
    try {
      // Pass __global__ for the general profile unlock
      const result = await verifyPayment(proof, '__global__');
      if (result.valid) {
        setPaySuccess(true);
        // Refresh useTier hook via event
        if (typeof window !== 'undefined') {
          window.dispatchEvent(new Event('nort-tier-refresh'));
        }
        setTimeout(() => onClose(), 1500);
      } else {
        setPayError(result.error || 'Payment invalid');
      }
    } catch {
      setPayError('Verification failed. Try again.');
    } finally {
      setPayLoading(false);
    }
  };

  const isLimit = reason === 'limit';

  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, zIndex: 1000,
        background: 'rgba(0,0,0,0.72)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: '16px', backdropFilter: 'blur(4px)',
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: 'var(--card)', border: '1px solid var(--border)',
          borderRadius: 16, padding: '28px 24px 24px',
          maxWidth: 420, width: '100%',
          boxShadow: '0 24px 64px rgba(0,0,0,0.5)',
        }}
      >
        {/* Header */}
        <div style={{ textAlign: 'center', marginBottom: 20 }}>
          <div style={{ fontSize: 36, marginBottom: 8, lineHeight: 1 }}>
            {isLimit ? '🔒' : '⚡'}
          </div>
          <h2 style={{
            fontSize: 18, fontWeight: 700, color: 'var(--white)',
            margin: '0 0 6px', fontFamily: 'DM Mono, monospace',
          }}>
            {isLimit ? `Daily limit reached (${used}/${limit})` : 'Premium feature'}
          </h2>
          <p style={{ color: 'var(--muted)', fontSize: 13, margin: 0, lineHeight: 1.5 }}>
            {isLimit
              ? `You've used all ${limit} free advice calls for today. Upgrade to keep going.`
              : 'This feature is available to premium users only.'}
          </p>
        </div>

        {/* Free vs Premium comparison table */}
        <div style={{
          background: 'var(--bg)', borderRadius: 10,
          overflow: 'hidden', border: '1px solid var(--border)', marginBottom: 20,
        }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', borderBottom: '1px solid var(--border)' }}>
            <div style={{ padding: '8px 12px', fontSize: 11, fontWeight: 700, color: 'var(--muted)', fontFamily: 'DM Mono, monospace', letterSpacing: '0.06em', textTransform: 'uppercase' }}>FREE</div>
            <div style={{ padding: '8px 12px', fontSize: 11, fontWeight: 700, color: '#F59E0B', fontFamily: 'DM Mono, monospace', letterSpacing: '0.06em', textTransform: 'uppercase', borderLeft: '1px solid var(--border)' }}>⚡ PREMIUM</div>
          </div>
          {FEATURES.map((row, i) => (
            <div key={i} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', borderBottom: i < FEATURES.length - 1 ? '1px solid var(--border)' : 'none' }}>
              <div style={{ padding: '9px 12px', fontSize: 12, color: 'var(--muted)' }}>{row.free}</div>
              <div style={{ padding: '9px 12px', fontSize: 12, color: 'var(--white)', borderLeft: '1px solid var(--border)', fontWeight: 500 }}>{row.premium}</div>
            </div>
          ))}
        </div>

        {/* Payment input section */}
        <div style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 12, color: 'var(--g4)', lineHeight: 1.6, marginBottom: 8, padding: '0 4px' }}>
            <strong>💳 How to unlock Premium:</strong><br />
            Send <strong>0.10 USDC</strong> to the NORT treasury on <strong>Base chain</strong>,
            then paste your transaction hash below.<br />
            <span style={{ color: 'var(--teal)', fontSize: 11 }}>
              🧪 Type <strong>"demo"</strong> to try Premium free (dev mode)
            </span>
          </div>
          <input
            type="text"
            placeholder="Paste tx hash or type 'demo'..."
            value={payInput}
            onChange={e => setPayInput(e.target.value)}
            style={{
              width: '100%', padding: '12px', borderRadius: 8,
              background: 'rgba(255,255,255,0.05)', border: '1px solid var(--border)',
              color: 'var(--white)', fontSize: 14, outline: 'none', marginBottom: 8,
              fontFamily: 'DM Mono, monospace'
            }}
          />
          {payError && <div style={{ color: 'var(--red)', fontSize: 12, marginBottom: 8, padding: '0 4px' }}>❌ {payError}</div>}
          {paySuccess && <div style={{ color: 'var(--green)', fontSize: 12, marginBottom: 8, padding: '0 4px' }}>✅ Payment confirmed! Unlocking...</div>}
        </div>

        {/* CTA buttons */}
        <button
          onClick={handlePay}
          disabled={payLoading || paySuccess || !payInput.trim()}
          style={{
            width: '100%', padding: '13px 0', borderRadius: 10, border: 'none',
            background: paySuccess ? 'var(--green)' : 'linear-gradient(135deg, #F59E0B, #EF4444)',
            color: '#000', fontSize: 14, fontWeight: 700,
            fontFamily: 'DM Mono, monospace', cursor: paySuccess || !payInput.trim() ? 'default' : 'pointer',
            letterSpacing: '0.04em', marginBottom: 10, opacity: payLoading || !payInput.trim() ? 0.5 : 1
          }}
        >
          {payLoading ? 'VERIFYING...' : paySuccess ? 'UNLOCKED ✓' : '⚡ UPGRADE TO PREMIUM'}
        </button>

        <button
          onClick={onClose}
          style={{
            width: '100%', padding: '10px 0', borderRadius: 10,
            border: '1px solid var(--border)', background: 'transparent',
            color: 'var(--muted)', fontSize: 13, cursor: 'pointer',
            fontFamily: 'DM Mono, monospace',
          }}
        >
          {isLimit ? 'Come back tomorrow' : 'Maybe later'}
        </button>
      </div>
    </div>
  );
}
