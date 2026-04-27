'use client';
import { useState } from 'react';
import { paperTrade } from '@/lib/api';
import { useTelegram } from '@/hooks/useTelegram';
import { useAuth } from '@/hooks/useAuth';

export default function TradeModal({ signal, initialSide = 'yes', onClose, onSuccess }) {
  const { haptic }                        = useTelegram();
  const { ready, isAuthed, walletAddress, login } = useAuth();
  const [side, setSide]     = useState(initialSide);
  const [amount, setAmount] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError]   = useState(null);

  if (!signal) return null;

  // Still initialising Privy
  if (!ready) {
    return (
      <div className="modal-overlay" onClick={onClose}>
        <div className="modal" onClick={e => e.stopPropagation()}>
          <div className="modal-handle" />
          <div className="modal-title">Loading...</div>
        </div>
      </div>
    );
  }

  // Not authenticated at all — show login
  if (!isAuthed) {
    return (
      <div className="modal-overlay" onClick={onClose}>
        <div className="modal" onClick={e => e.stopPropagation()}>
          <div className="modal-handle" />
          <div className="modal-title">Login Required</div>
          <div className="modal-sub">Sign in to place paper trades</div>
          <div className="modal-q" style={{ textAlign: 'center', marginBottom: 20 }}>
            Connect your wallet or sign in with Google to start trading with $1,000 paper USDC.
          </div>
          <button className="modal-cta" onClick={() => { haptic.medium?.(); login(); }}>
            Sign In / Connect Wallet
          </button>
        </div>
      </div>
    );
  }

  // FIX: clamp yes to 1-99 so price is never 0 (which causes Infinity shares/payout)
  const yesOdds = Math.max(1, Math.min(99, signal.yes || 50));
  const price  = side === 'yes' ? yesOdds / 100 : (100 - yesOdds) / 100;
  const shares = amount && parseFloat(amount) > 0 ? (parseFloat(amount) / price).toFixed(1) : '—';
  const payout = amount && parseFloat(amount) > 0 ? (parseFloat(amount) / price).toFixed(2) : '—';

  const submit = async () => {
    if (!amount || parseFloat(amount) <= 0) return;
    setError(null);
    haptic.medium?.();
    setLoading(true);
    try {
      const trade = await paperTrade({
        marketId: signal.id,
        side,
        amount:   parseFloat(amount),
        price,
        question: signal.q,   // pass directly — avoids wrong DB lookup
      });
      haptic.success?.();
      onSuccess?.(trade);
      onClose();
    } catch (err) {
      haptic.error?.();
      setError(err.message || 'Trade failed. Check your balance.');
    } finally {
      setLoading(false);
    }
  };

  return (
    // market-p: modal background changed from blue-tint to pure black to match NORT dark theme
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()} style={{ background: 'rgba(10,10,10,0.97)' }}>
        <div className="modal-handle" />

        <div className="modal-title">Paper Trade</div>
        <div className="modal-sub">SIMULATION ONLY · NO REAL FUNDS</div>

        <div className="modal-q">{signal.q}</div>

        {/* YES / NO toggle */}
        <div className="modal-sides">
          <button
            className={`side-btn ${side === 'yes' ? 'active-yes' : ''}`}
            onClick={() => { setSide('yes'); haptic.light?.(); }}
          >
            <span className="side-label">▲ YES</span>
            <span className="side-price">{yesOdds}¢</span>
          </button>
          <button
            className={`side-btn ${side === 'no' ? 'active-no' : ''}`}
            onClick={() => { setSide('no'); haptic.light?.(); }}
          >
            <span className="side-label">▼ NO</span>
            <span className="side-price">{100 - yesOdds}¢</span>
          </button>
        </div>

        {/* Amount input */}
        <div className="modal-input-label">Amount (paper USDC)</div>
        <div className="modal-input-wrap">
          <span className="modal-input-prefix">$</span>
          <input
            className="modal-input"
            type="number"
            placeholder="0.00"
            value={amount}
            onChange={e => setAmount(e.target.value)}
            inputMode="decimal"
          />
        </div>

        {/* Payout preview */}
        <div className="modal-payout">
          <div>
            <div className="payout-label">Shares</div>
            <div className="payout-val">{shares}</div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div className="payout-label">Max Payout</div>
            <div className="payout-val">{payout !== '—' ? `$${payout}` : '—'}</div>
          </div>
        </div>

        {error && (
          <div style={{ color: 'var(--red)', fontSize: 12, textAlign: 'center', marginBottom: 8 }}>
            {error}
          </div>
        )}

        <button
          className="modal-cta"
          onClick={submit}
          disabled={!amount || loading}
        >
          {loading ? 'Placing...' : `Place ${side.toUpperCase()} Trade`}
        </button>
      </div>
    </div>
  );
}
