'use client';
/**
 * PremiumGate.jsx
 *
 * Shown when a free user hits their advice limit OR tries a premium feature.
 *
 * Upgrade flow (primary):
 *   1. Fetches payment details from backend (treasury address, amount, chain)
 *   2. Uses the user's connected Privy wallet to send USDC on Base
 *   3. Waits for on-chain confirmation (polls Base RPC)
 *   4. Calls /x402/upgrade with the confirmed tx hash
 *   5. Flips tier badge to ⚡ PREMIUM instantly
 *
 * Fallback (manual):
 *   Users can expand a "manual" panel and paste a tx hash directly.
 *
 * Props:
 *   open    — boolean
 *   onClose — callback
 *   reason  — 'limit' | 'feature'
 *   used    — how many calls used this window (shown in limit mode)
 */

import { useEffect, useState, useRef } from 'react';
import { useWallets } from '@privy-io/react-auth';
import { verifyPayment, getUpgradePaymentDetails } from '@/lib/api';
import { useTier } from '@/hooks/useTier';

const FEATURES = [
  { free: '10 AI calls per 6h window',  premium: 'Unlimited AI advice & chat' },
  { free: 'Brief summary only',         premium: 'Full deep-dive: why trending + risks' },
  { free: 'No entry/exit targets',      premium: 'Exact odds targets + position sizing' },
  { free: 'Standard AI (Llama 3.1 8B)',  premium: 'Claude Sonnet — smarter analysis' },
  { free: 'No conversation memory',     premium: 'AI remembers your prior questions' },
  { free: 'English only',               premium: 'Swahili + English support' },
  { free: 'No general chat',            premium: 'Full general chat with NORT Bot' },
];

// ── Helpers ───────────────────────────────────────────────────────────────────

/** Encode ERC-20 transfer(address,uint256) calldata without any extra deps */
function encodeUsdcTransfer(toAddress, amountRaw) {
  const selector = 'a9059cbb';
  const paddedTo = toAddress.toLowerCase().replace('0x', '').padStart(64, '0');
  const paddedAmt = BigInt(amountRaw).toString(16).padStart(64, '0');
  return '0x' + selector + paddedTo + paddedAmt;
}

/** Poll Base RPC until tx is mined (max ~60 s) */
async function waitForReceipt(txHash, maxAttempts = 20) {
  for (let i = 0; i < maxAttempts; i++) {
    try {
      const res = await fetch('https://mainnet.base.org', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          jsonrpc: '2.0', method: 'eth_getTransactionReceipt',
          params: [txHash], id: 1,
        }),
      });
      const data = await res.json();
      if (data.result) {
        if (data.result.status === '0x1') return true;
        if (data.result.status === '0x0') throw new Error('Transaction reverted on-chain');
      }
    } catch (e) {
      if (e.message.includes('reverted')) throw e;
    }
    await new Promise(r => setTimeout(r, 3000));
  }
  throw new Error('Transaction confirmation timed out. Please paste the hash manually below.');
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function PremiumGate({ open, onClose, reason = 'limit', used = 10, limit = 10 }) {
  const { optimisticUpgrade } = useTier();
  const { wallets } = useWallets();

  // Payment details from backend
  const [payInfo, setPayInfo]       = useState(null);
  const [infoError, setInfoError]   = useState('');

  // Wallet-pay state
  const [payStep, setPayStep]       = useState('idle'); // idle | sending | waiting | verifying | done | error
  const [payError, setPayError]     = useState('');
  const [txHashResult, setTxHash]   = useState('');

  // Manual fallback
  const [showManual, setShowManual] = useState(false);
  const [manualInput, setManualInput] = useState('');
  const [manualLoading, setManualLoading] = useState(false);
  const [manualError, setManualError] = useState('');

  const closedRef = useRef(false);

  // Reset on open
  useEffect(() => {
    if (!open) { closedRef.current = false; return; }
    setPayStep('idle');
    setPayError('');
    setTxHash('');
    setShowManual(false);
    setManualInput('');
    setManualError('');
    setInfoError('');

    // Fetch payment details
    getUpgradePaymentDetails()
      .then(setPayInfo)
      .catch(() => setInfoError('Could not load payment details. Try refreshing.'));

    const handler = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, onClose]);

  if (!open) return null;

  // ── Active wallet ───────────────────────────────────────────────────────────
  const activeWallet = wallets?.find(w => w.walletClientType === 'privy') || wallets?.[0] || null;
  const canPayWithWallet = !!activeWallet && !!payInfo?.treasury && !!payInfo?.usdc_contract;

  // ── Pay with wallet ─────────────────────────────────────────────────────────
  const handleWalletPay = async () => {
    if (!canPayWithWallet || payStep !== 'idle') return;
    setPayStep('sending');
    setPayError('');

    try {
      // USDC has 6 decimals — $1.00 = 1_000_000 raw units
      const amountRaw = Math.round(payInfo.amount * 1_000_000);
      const calldata  = encodeUsdcTransfer(payInfo.treasury, amountRaw);

      // Get Ethereum provider from Privy wallet
      const provider = await activeWallet.getEthereumProvider();

      // Ensure wallet is on Base
      try {
        await provider.request({
          method: 'wallet_switchEthereumChain',
          params: [{ chainId: '0x2105' }], // 8453 hex
        });
      } catch { /* wallet may already be on Base */ }

      // Send USDC transfer
      const txHash = await provider.request({
        method: 'eth_sendTransaction',
        params: [{
          from: activeWallet.address,
          to: payInfo.usdc_contract,
          data: calldata,
          value: '0x0',
        }],
      });

      setTxHash(txHash);
      setPayStep('waiting');

      // Poll until mined
      await waitForReceipt(txHash);
      setPayStep('verifying');

      // Tell backend to verify and record the payment
      const result = await verifyPayment(txHash, '__global__');
      if (result.valid) {
        setPayStep('done');
        optimisticUpgrade();
        setTimeout(() => { if (!closedRef.current) onClose(); }, 1200);
      } else {
        setPayStep('error');
        setPayError(result.error || 'Backend verification failed. Please paste the tx hash manually below.');
        setShowManual(true);
        setManualInput(txHash);
      }
    } catch (e) {
      setPayStep('error');
      const msg = e?.message || String(e);
      if (msg.toLowerCase().includes('user rejected') || msg.toLowerCase().includes('denied')) {
        setPayError('Transaction cancelled.');
      } else if (msg.includes('timed out')) {
        setPayError(msg);
        setShowManual(true);
        if (txHashResult) setManualInput(txHashResult);
      } else {
        setPayError(msg || 'Payment failed. Please try again.');
      }
    }
  };

  // ── Manual hash submit ──────────────────────────────────────────────────────
  const handleManualPay = async () => {
    const proof = manualInput.trim();
    if (!proof) return;
    setManualLoading(true);
    setManualError('');
    try {
      const result = await verifyPayment(proof, '__global__');
      if (result.valid) {
        setPayStep('done');
        optimisticUpgrade();
        setTimeout(() => { if (!closedRef.current) onClose(); }, 1200);
      } else {
        setManualError(result.error || 'Verification failed.');
      }
    } catch {
      setManualError('Verification failed. Try again.');
    } finally {
      setManualLoading(false);
    }
  };

  const isLimit   = reason === 'limit';
  const isDone    = payStep === 'done';
  const isSending = payStep === 'sending';
  const isWaiting = payStep === 'waiting';
  const isVerifying = payStep === 'verifying';
  const busy      = isSending || isWaiting || isVerifying;

  const walletBtnLabel = () => {
    if (isDone)       return 'UNLOCKED ✓';
    if (isSending)    return 'Waiting for wallet confirmation...';
    if (isWaiting)    return 'Waiting for on-chain confirmation...';
    if (isVerifying)  return 'Verifying payment...';
    if (payStep === 'error') return 'Try Again';
    if (!payInfo)     return 'Loading payment details...';
    if (!canPayWithWallet) return 'Connect a wallet to pay';
    return `Pay $${payInfo?.amount?.toFixed(2) ?? '1.00'} USDC — Unlock Premium`;
  };

  return (
    <div
      onClick={() => { closedRef.current = true; onClose(); }}
      style={{
        position: 'fixed', inset: 0, zIndex: 1000,
        background: 'rgba(0,0,0,0.75)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: '16px', backdropFilter: 'blur(6px)',
      }}
    >
      <div
        onClick={e => e.stopPropagation()}
        style={{
          background: 'var(--card)', border: '1px solid var(--border)',
          borderRadius: 18, padding: '28px 24px 24px',
          maxWidth: 440, width: '100%',
          boxShadow: '0 24px 80px rgba(0,0,0,0.6)',
          maxHeight: '90vh', overflowY: 'auto',
        }}
      >
        {/* ── Header ── */}
        <div style={{ textAlign: 'center', marginBottom: 20 }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: '#F59E0B', fontFamily: 'DM Mono, monospace', letterSpacing: '0.06em', marginBottom: 6 }}>
            {isLimit ? 'LIMIT REACHED' : 'PREMIUM FEATURE'}
          </div>
          <h2 style={{ fontSize: 18, fontWeight: 700, color: 'var(--white)', margin: '0 0 6px', fontFamily: 'DM Mono, monospace' }}>
            {isLimit ? `${used}/${limit} calls used` : 'Unlock Premium'}
          </h2>
          <p style={{ color: 'var(--muted)', fontSize: 13, margin: 0, lineHeight: 1.5 }}>
            {isLimit
              ? `You've used all ${limit} free calls this window. Upgrade for unlimited access.`
              : 'This feature is available to Premium users only.'}
          </p>
        </div>

        {/* ── Feature comparison ── */}
        <div style={{
          background: 'var(--bg)', borderRadius: 10,
          overflow: 'hidden', border: '1px solid var(--border)', marginBottom: 20,
        }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', borderBottom: '1px solid var(--border)' }}>
            <div style={{ padding: '8px 12px', fontSize: 11, fontWeight: 700, color: 'var(--muted)', fontFamily: 'DM Mono, monospace', letterSpacing: '0.06em', textTransform: 'uppercase' }}>FREE</div>
            <div style={{ padding: '8px 12px', fontSize: 11, fontWeight: 700, color: '#F59E0B', fontFamily: 'DM Mono, monospace', letterSpacing: '0.06em', textTransform: 'uppercase', borderLeft: '1px solid var(--border)' }}>PREMIUM</div>
          </div>
          {FEATURES.map((row, i) => (
            <div key={i} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', borderBottom: i < FEATURES.length - 1 ? '1px solid var(--border)' : 'none' }}>
              <div style={{ padding: '9px 12px', fontSize: 12, color: 'var(--muted)' }}>{row.free}</div>
              <div style={{ padding: '9px 12px', fontSize: 12, color: 'var(--white)', borderLeft: '1px solid var(--border)', fontWeight: 500 }}>{row.premium}</div>
            </div>
          ))}
        </div>

        {/* ── Info error ── */}
        {infoError && (
          <div style={{ color: 'var(--red)', fontSize: 12, marginBottom: 12, textAlign: 'center' }}>{infoError}</div>
        )}

        {/* ── Payment info pill ── */}
        {payInfo && !isDone && (
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
            padding: '8px 14px', borderRadius: 8, marginBottom: 14,
            background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.2)',
            fontSize: 12, color: '#F59E0B', fontFamily: 'DM Mono, monospace',
          }}>
            <span>One-time unlock · <strong>${payInfo.amount.toFixed(2)} USDC</strong> on <strong>Base</strong></span>
          </div>
        )}

        {/* ── Status messages ── */}
        {txHashResult && (isWaiting || isVerifying) && (
          <div style={{
            fontSize: 11, color: 'var(--muted)', fontFamily: 'DM Mono, monospace',
            textAlign: 'center', marginBottom: 10, wordBreak: 'break-all',
          }}>
            Tx: {txHashResult.slice(0, 14)}...{txHashResult.slice(-8)}
          </div>
        )}

        {/* ── Error message ── */}
        {payStep === 'error' && payError && (
          <div style={{ color: 'var(--red)', fontSize: 12, marginBottom: 10, padding: '8px 12px', background: 'rgba(239,68,68,0.08)', borderRadius: 6, lineHeight: 1.5 }}>
            {payError}
          </div>
        )}

        {/* ── Primary CTA — Pay with Wallet ── */}
        <button
          id="premium-pay-wallet-btn"
          onClick={payStep === 'error' ? () => { setPayStep('idle'); setPayError(''); } : handleWalletPay}
          disabled={busy || isDone || (!canPayWithWallet && payStep === 'idle')}
          style={{
            width: '100%', padding: '14px 0', borderRadius: 10, border: 'none',
            background: isDone
              ? 'var(--green)'
              : busy
              ? 'rgba(245,158,11,0.3)'
              : 'linear-gradient(135deg, #F59E0B 0%, #EF4444 100%)',
            color: isDone ? '#000' : busy ? '#F59E0B' : '#000',
            fontSize: 14, fontWeight: 700,
            fontFamily: 'DM Mono, monospace', cursor: busy || isDone ? 'default' : 'pointer',
            letterSpacing: '0.04em', marginBottom: 8,
            opacity: (!canPayWithWallet && payStep === 'idle') ? 0.5 : 1,
            transition: 'all 0.3s',
            position: 'relative',
          }}
        >
          {busy && (
            <span style={{
              display: 'inline-block', width: 12, height: 12,
              border: '2px solid #F59E0B', borderTopColor: 'transparent',
              borderRadius: '50%', animation: 'spin 0.8s linear infinite',
              marginRight: 8, verticalAlign: 'middle',
            }} />
          )}
          {walletBtnLabel()}
        </button>

        {/* ── No wallet hint ── */}
        {!canPayWithWallet && payStep === 'idle' && (
          <div style={{ fontSize: 11, color: 'var(--muted)', textAlign: 'center', marginBottom: 8, lineHeight: 1.5 }}>
            No wallet connected. Use the manual option below.
          </div>
        )}

        {/* ── Manual tx hash fallback ── */}
        {!isDone && (
          <div style={{ marginBottom: 8 }}>
            <button
              onClick={() => setShowManual(v => !v)}
              style={{
                background: 'none', border: 'none', cursor: 'pointer',
                color: 'var(--muted)', fontSize: 12, width: '100%',
                padding: '6px 0', fontFamily: 'DM Mono, monospace',
                textDecoration: 'underline', textUnderlineOffset: 2,
              }}
            >
              {showManual ? '▲ Hide' : '▼ Already paid? Paste tx hash manually'}
            </button>
            {showManual && (
              <div style={{ marginTop: 8 }}>
                <div style={{ fontSize: 11, color: 'var(--g4)', lineHeight: 1.6, marginBottom: 6, padding: '0 2px' }}>
                  Send <strong>${payInfo?.amount?.toFixed(2) ?? '1.00'} USDC</strong> to the NORT treasury on <strong>Base chain</strong>, then paste your tx hash below.
                  {payInfo?.treasury && (
                    <><br /><span style={{ color: 'var(--teal)', fontFamily: 'DM Mono, monospace', fontSize: 10, wordBreak: 'break-all' }}>
                      Treasury: {payInfo.treasury}
                    </span></>
                  )}
                </div>
                <input
                  type="text"
                  placeholder="Paste 0x... tx hash or type 'demo'"
                  value={manualInput}
                  onChange={e => setManualInput(e.target.value)}
                  style={{
                    width: '100%', padding: '11px 12px', borderRadius: 8,
                    background: 'rgba(255,255,255,0.05)', border: '1px solid var(--border)',
                    color: 'var(--white)', fontSize: 13, outline: 'none',
                    fontFamily: 'DM Mono, monospace', marginBottom: 6, boxSizing: 'border-box',
                  }}
                />
                {manualError && (
                  <div style={{ color: 'var(--red)', fontSize: 12, marginBottom: 6 }}>{manualError}</div>
                )}
                <button
                  onClick={handleManualPay}
                  disabled={manualLoading || !manualInput.trim()}
                  style={{
                    width: '100%', padding: '10px 0', borderRadius: 8, border: 'none',
                    background: 'rgba(255,255,255,0.08)', color: 'var(--white)',
                    fontSize: 13, fontWeight: 600, cursor: manualLoading || !manualInput.trim() ? 'default' : 'pointer',
                    fontFamily: 'DM Mono, monospace', opacity: manualLoading || !manualInput.trim() ? 0.5 : 1,
                  }}
                >
                  {manualLoading ? 'Verifying...' : 'Verify Payment'}
                </button>
              </div>
            )}
          </div>
        )}

        {/* ── Cancel ── */}
        {!isDone && (
          <button
            onClick={() => { closedRef.current = true; onClose(); }}
            style={{
              width: '100%', padding: '10px 0', borderRadius: 10,
              border: '1px solid var(--border)', background: 'transparent',
              color: 'var(--muted)', fontSize: 13, cursor: 'pointer',
              fontFamily: 'DM Mono, monospace',
            }}
          >
            {isLimit ? 'Come back later' : 'Maybe later'}
          </button>
        )}
      </div>

      {/* Spinner keyframes */}
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
