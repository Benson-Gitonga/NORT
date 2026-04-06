'use client';
import React, { useEffect, useState, useCallback } from 'react';
import { useAuth } from '@/hooks/useAuth';
import { useTelegram } from '@/hooks/useTelegram';
import { useTradingMode } from '@/components/TradingModeContext';
import AuthGate from '@/components/AuthGate';
import Navbar from '@/components/Navbar';
import {
  getFullWallet,
  getPretiumRate,
  createOnramp,
  createOfframp,
  getPretiumTransaction,
  getPretiumTransactions,
  getPretiumSettlementAddress,
} from '@/lib/api';

// ── Status helpers ───────────────────────────────────────────────────────────
const STATUS_LABELS = {
  pending: 'Initiating...',
  processing: 'Processing...',
  payment_confirmed: 'Payment received',
  releasing_asset: 'Releasing crypto...',
  completed: 'Completed',
  failed: 'Failed',
  canceled: 'Canceled',
  refunded: 'Refunded',
};

const STATUS_COLOR = s => {
  if (s === 'completed') return 'var(--green)';
  if (['failed', 'canceled'].includes(s)) return 'var(--red)';
  if (s === 'refunded') return 'var(--muted)';
  return '#F59E0B';
};

const TERMINAL = new Set(['completed', 'failed', 'canceled', 'refunded']);

export default function WalletPage() {
  const { user, walletAddress } = useAuth();
  const { haptic } = useTelegram();
  const { mode } = useTradingMode();
  const isReal = mode === 'real';

  // ── State ──
  const [wallet, setWallet] = useState(null);
  const [tab, setTab] = useState('deposit');         // deposit | withdraw | history
  const [loading, setLoading] = useState(true);

  // Form state
  const [amount, setAmount] = useState('');
  const [phone, setPhone] = useState('');

  // Rate
  const [rate, setRate] = useState(null);
  const [rateLoading, setRateLoading] = useState(false);

  // Active transaction
  const [activeTx, setActiveTx] = useState(null);
  const [txLoading, setTxLoading] = useState(false);
  const [txError, setTxError] = useState('');

  // Off-ramp: settlement address + tx hash
  const [settlementAddress, setSettlementAddress] = useState('');
  const [txHash, setTxHash] = useState('');

  // History
  const [transactions, setTransactions] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  // ── Load wallet ──
  useEffect(() => {
    getFullWallet()
      .then(setWallet)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  // ── Load history when tab switches ──
  useEffect(() => {
    if (tab === 'history') {
      setHistoryLoading(true);
      getPretiumTransactions()
        .then(d => setTransactions(d.transactions || []))
        .catch(() => {})
        .finally(() => setHistoryLoading(false));
    }
  }, [tab]);

  // ── Fetch exchange rate on mount + when tab changes ──
  useEffect(() => {
    if (tab === 'deposit' || tab === 'withdraw') {
      setRateLoading(true);
      getPretiumRate()
        .then(setRate)
        .catch(() => {})
        .finally(() => setRateLoading(false));
    }
  }, [tab]);

  // ── Fetch settlement address for off-ramp ──
  useEffect(() => {
    if (tab === 'withdraw') {
      getPretiumSettlementAddress()
        .then(d => setSettlementAddress(d.address || ''))
        .catch(() => {});
    }
  }, [tab]);

  // ── Poll active transaction ──
  useEffect(() => {
    if (!activeTx || TERMINAL.has(activeTx.status)) return;
    const interval = setInterval(async () => {
      try {
        const tx = await getPretiumTransaction(activeTx.transaction_id);
        setActiveTx(tx);
        if (TERMINAL.has(tx.status)) {
          getFullWallet().then(setWallet).catch(() => {});
        }
      } catch {}
    }, 5000);
    return () => clearInterval(interval);
  }, [activeTx]);

  // ── Computed values ──
  const buyingRate = rate?.buying_rate;
  const sellingRate = rate?.selling_rate;

  const estimatedReceive = (() => {
    const num = parseFloat(amount);
    if (!num || num <= 0) return null;
    if (tab === 'deposit' && buyingRate) return (num / buyingRate).toFixed(2);
    if (tab === 'withdraw' && sellingRate) return Math.round(num * sellingRate).toLocaleString();
    return null;
  })();

  // ── Submit Deposit (On-Ramp) ──
  const handleDeposit = useCallback(async () => {
    const numAmount = parseInt(amount, 10);
    if (!numAmount || numAmount <= 0) { setTxError('Enter a valid KES amount'); return; }
    if (!phone.trim()) { setTxError('Enter your M-Pesa phone number'); return; }

    setTxLoading(true);
    setTxError('');
    haptic?.medium?.();
    try {
      const result = await createOnramp({
        amount: numAmount,
        phoneNumber: phone.trim(),
        walletAddress: walletAddress || '',
        telegramUserId: walletAddress?.toLowerCase() || null,
      });
      setActiveTx(result);
    } catch (e) {
      setTxError(e.message);
    } finally {
      setTxLoading(false);
    }
  }, [amount, phone, walletAddress, haptic]);

  // ── Submit Withdraw (Off-Ramp) ──
  const handleWithdraw = useCallback(async () => {
    const numAmount = parseFloat(amount);
    if (!numAmount || numAmount < 1) { setTxError('Minimum withdrawal is 1 USDC'); return; }
    if (!phone.trim()) { setTxError('Enter your M-Pesa phone number'); return; }
    if (!txHash.trim()) { setTxError('Enter the transaction hash of your crypto transfer'); return; }

    setTxLoading(true);
    setTxError('');
    haptic?.medium?.();
    try {
      const result = await createOfframp({
        amountCrypto: numAmount,
        phoneNumber: phone.trim(),
        walletAddress: walletAddress || '',
        transactionHash: txHash.trim(),
        telegramUserId: walletAddress?.toLowerCase() || null,
      });
      setActiveTx(result);
    } catch (e) {
      setTxError(e.message);
    } finally {
      setTxLoading(false);
    }
  }, [amount, phone, txHash, walletAddress, haptic]);

  // ── Reset to new transaction ──
  const handleNewTransaction = () => {
    setActiveTx(null);
    setAmount('');
    setTxError('');
    setTxHash('');
  };

  const realBalance = wallet?.realBalanceUsdc ?? 0;

  return (
    <AuthGate>
      <div className={`app${isReal ? ' real-mode' : ''}`}>
        <div className="header">
          <div className="header-logo">Wallet</div>
          <div className="header-right">
            <div className="live-pill" style={{ borderColor: isReal ? '#F59E0B' : undefined, color: isReal ? '#F59E0B' : undefined }}>
              <span className="live-dot" style={{ background: isReal ? '#F59E0B' : undefined }} />
              {isReal ? 'Real' : 'Paper'}
            </div>
          </div>
        </div>

        <div className="scroll">
          {/* ── Balance Card ── */}
          <div className="fu d1" style={{
            background: 'var(--glass-bg)',
            border: '1px solid var(--glass-border)',
            borderRadius: 'var(--r)',
            padding: '20px',
            textAlign: 'center',
            marginBottom: 12,
          }}>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', fontFamily: 'DM Mono, monospace', letterSpacing: '0.08em', textTransform: 'uppercase' }}>
              USDC Balance
            </div>
            <div style={{ fontSize: 32, fontWeight: 700, fontFamily: 'Syne, sans-serif', marginTop: 4 }}>
              ${loading ? '...' : realBalance.toFixed(2)}
            </div>
            {rate && (
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4, fontFamily: 'DM Mono, monospace' }}>
                1 USDC = KES {Number(rate.buying_rate || 0).toFixed(2)}
              </div>
            )}
          </div>

          {/* ── Tab Switcher ── */}
          {!activeTx && (
            <div className="fu d2" style={{
              display: 'flex',
              gap: 4,
              background: 'var(--glass-bg)',
              border: '1px solid var(--glass-border)',
              borderRadius: 'var(--rsm)',
              padding: 4,
              marginBottom: 12,
            }}>
              {[
                { key: 'deposit', label: 'Deposit' },
                { key: 'withdraw', label: 'Withdraw' },
                { key: 'history', label: 'History' },
              ].map(t => (
                <button
                  key={t.key}
                  onClick={() => { setTab(t.key); setAmount(''); setTxError(''); setTxHash(''); }}
                  style={{
                    flex: 1,
                    padding: '10px 0',
                    borderRadius: 8,
                    border: 'none',
                    cursor: 'pointer',
                    fontSize: 13,
                    fontWeight: 600,
                    fontFamily: 'Plus Jakarta Sans, sans-serif',
                    transition: 'all 0.2s',
                    background: tab === t.key ? 'var(--teal-dim)' : 'transparent',
                    color: tab === t.key ? 'var(--teal)' : 'var(--text-muted)',
                  }}
                >
                  {t.label}
                </button>
              ))}
            </div>
          )}

          {/* ── Active Transaction View ── */}
          {activeTx && (
            <div className="fu d3" style={{
              background: 'var(--glass-bg)',
              border: '1px solid var(--glass-border)',
              borderRadius: 'var(--r)',
              padding: 20,
              marginBottom: 12,
            }}>
              <div style={{ textAlign: 'center', marginBottom: 16 }}>
                <div style={{ fontSize: 12, color: 'var(--text-muted)', fontFamily: 'DM Mono, monospace', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  {activeTx.type === 'onramp' ? 'Deposit' : 'Withdraw'} Status
                </div>
                <div style={{
                  fontSize: 16,
                  fontWeight: 700,
                  color: STATUS_COLOR(activeTx.status),
                  marginTop: 8,
                  fontFamily: 'DM Mono, monospace',
                }}>
                  {STATUS_LABELS[activeTx.status] || activeTx.status}
                </div>
              </div>

              {/* Transaction details */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {activeTx.amount_fiat != null && (
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
                    <span style={{ color: 'var(--text-muted)' }}>KES Amount</span>
                    <span>KES {Number(activeTx.amount_fiat).toLocaleString()}</span>
                  </div>
                )}
                {activeTx.amount_crypto != null && (
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
                    <span style={{ color: 'var(--text-muted)' }}>USDC Amount</span>
                    <span>${Number(activeTx.amount_crypto).toFixed(2)}</span>
                  </div>
                )}
                {activeTx.exchange_rate != null && (
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
                    <span style={{ color: 'var(--text-muted)' }}>Rate</span>
                    <span>1 USDC = KES {Number(activeTx.exchange_rate).toFixed(2)}</span>
                  </div>
                )}
                {activeTx.tx_hash && (
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
                    <span style={{ color: 'var(--text-muted)' }}>Tx Hash</span>
                    <span style={{ fontFamily: 'DM Mono, monospace', fontSize: 11 }}>{activeTx.tx_hash.slice(0, 10)}...</span>
                  </div>
                )}
              </div>

              {/* STK Push waiting state (on-ramp) */}
              {activeTx.type === 'onramp' && ['pending', 'processing'].includes(activeTx.status) && (
                <div style={{ marginTop: 16, textAlign: 'center', fontSize: 13, color: 'var(--text-secondary)' }}>
                  Check your phone for the M-Pesa payment prompt. Enter your PIN to complete.
                </div>
              )}

              {/* Processing states */}
              {['payment_confirmed', 'releasing_asset'].includes(activeTx.status) && (
                <div style={{ marginTop: 16, textAlign: 'center' }}>
                  <div style={{ fontSize: 20, marginBottom: 4 }}>&#8987;</div>
                  <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                    {activeTx.type === 'onramp' ? 'Releasing USDC to your wallet...' : 'Sending KES to your M-Pesa...'}
                  </div>
                </div>
              )}

              {activeTx.type === 'offramp' && activeTx.status === 'processing' && (
                <div style={{ marginTop: 16, textAlign: 'center' }}>
                  <div style={{ fontSize: 20, marginBottom: 4 }}>&#8987;</div>
                  <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                    Verifying crypto payment and processing M-Pesa transfer...
                  </div>
                </div>
              )}

              {/* Completed */}
              {activeTx.status === 'completed' && (
                <div style={{ marginTop: 16, textAlign: 'center' }}>
                  <div style={{ fontSize: 28, marginBottom: 4 }}>&#10003;</div>
                  <div style={{ fontSize: 13, color: 'var(--green)' }}>
                    {activeTx.type === 'onramp'
                      ? `+$${Number(activeTx.amount_crypto || 0).toFixed(2)} USDC deposited!`
                      : `KES ${Number(activeTx.amount_fiat || 0).toLocaleString()} sent to M-Pesa!`}
                  </div>
                </div>
              )}

              {txError && (
                <div style={{ color: 'var(--red)', fontSize: 12, marginTop: 8, textAlign: 'center' }}>{txError}</div>
              )}

              {/* Actions */}
              <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
                {TERMINAL.has(activeTx.status) && (
                  <button className="modal-cta" onClick={handleNewTransaction} style={{ flex: 1 }}>
                    New Transaction
                  </button>
                )}
              </div>
            </div>
          )}

          {/* ── Deposit Form (On-Ramp: KES -> USDC) ── */}
          {!activeTx && tab === 'deposit' && (
            <div className="fu d3">
              <div style={{
                background: 'var(--glass-bg)',
                border: '1px solid var(--glass-border)',
                borderRadius: 'var(--r)',
                padding: 16,
                marginBottom: 12,
              }}>
                <div style={{ fontSize: 12, color: 'var(--text-muted)', fontFamily: 'DM Mono, monospace', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Amount (KES)
                </div>
                <div className="modal-input-wrap">
                  <input
                    className="modal-input"
                    type="text"
                    inputMode="numeric"
                    placeholder="e.g. 1000"
                    value={amount}
                    onChange={e => setAmount(e.target.value.replace(/[^0-9]/g, ''))}
                  />
                </div>

                <div style={{ display: 'flex', gap: 6, marginTop: 8, flexWrap: 'wrap' }}>
                  {[500, 1000, 2500, 5000].map(v => (
                    <button
                      key={v}
                      className="chip-btn"
                      onClick={() => setAmount(String(v))}
                      style={{ fontSize: 12, padding: '4px 10px' }}
                    >
                      KES {v.toLocaleString()}
                    </button>
                  ))}
                </div>

                {/* Estimate */}
                {estimatedReceive && (
                  <div style={{
                    marginTop: 12,
                    padding: '8px 12px',
                    background: 'var(--teal-dim)',
                    borderRadius: 8,
                    display: 'flex',
                    justifyContent: 'space-between',
                    fontSize: 13,
                  }}>
                    <span style={{ color: 'var(--text-muted)' }}>You receive (est.)</span>
                    <span style={{ fontWeight: 700, color: 'var(--green)' }}>${estimatedReceive} USDC</span>
                  </div>
                )}

                {/* Phone */}
                <div style={{ marginTop: 12 }}>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>M-Pesa Phone Number</div>
                  <div className="modal-input-wrap">
                    <input
                      className="modal-input"
                      type="tel"
                      placeholder="+254 7XX XXX XXX"
                      value={phone}
                      onChange={e => setPhone(e.target.value)}
                    />
                  </div>
                </div>

                {txError && (
                  <div style={{ color: 'var(--red)', fontSize: 12, marginTop: 8, textAlign: 'center' }}>{txError}</div>
                )}

                <button
                  className="modal-cta"
                  onClick={handleDeposit}
                  disabled={txLoading || !amount || !phone.trim()}
                  style={{ width: '100%', marginTop: 12 }}
                >
                  {txLoading ? 'Processing...' : `Deposit KES ${Number(amount || 0).toLocaleString()}`}
                </button>

                <div style={{ fontSize: 10, color: 'var(--text-muted)', textAlign: 'center', marginTop: 8 }}>
                  An M-Pesa STK push will be sent to your phone.
                </div>
              </div>
            </div>
          )}

          {/* ── Withdraw Form (Off-Ramp: USDC -> KES) ── */}
          {!activeTx && tab === 'withdraw' && (
            <div className="fu d3">
              <div style={{
                background: 'var(--glass-bg)',
                border: '1px solid var(--glass-border)',
                borderRadius: 'var(--r)',
                padding: 16,
                marginBottom: 12,
              }}>
                <div style={{ fontSize: 12, color: 'var(--text-muted)', fontFamily: 'DM Mono, monospace', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Amount (USDC)
                </div>
                <div className="modal-input-wrap">
                  <input
                    className="modal-input"
                    type="text"
                    inputMode="decimal"
                    placeholder="e.g. 10"
                    value={amount}
                    onChange={e => setAmount(e.target.value.replace(/[^0-9.]/g, ''))}
                  />
                </div>

                <div style={{ display: 'flex', gap: 6, marginTop: 8, flexWrap: 'wrap' }}>
                  {[5, 10, 25, 50].map(v => (
                    <button
                      key={v}
                      className="chip-btn"
                      onClick={() => setAmount(String(v))}
                      disabled={v > realBalance}
                      style={{ fontSize: 12, padding: '4px 10px', opacity: v > realBalance ? 0.4 : 1 }}
                    >
                      ${v}
                    </button>
                  ))}
                  <button
                    className="chip-btn"
                    onClick={() => setAmount(String(realBalance))}
                    disabled={realBalance <= 0}
                    style={{ fontSize: 12, padding: '4px 10px', opacity: realBalance <= 0 ? 0.4 : 1 }}
                  >
                    Max
                  </button>
                </div>

                {/* Estimate */}
                {estimatedReceive && (
                  <div style={{
                    marginTop: 12,
                    padding: '8px 12px',
                    background: 'var(--teal-dim)',
                    borderRadius: 8,
                    display: 'flex',
                    justifyContent: 'space-between',
                    fontSize: 13,
                  }}>
                    <span style={{ color: 'var(--text-muted)' }}>You receive (est.)</span>
                    <span style={{ fontWeight: 700, color: 'var(--green)' }}>KES {estimatedReceive}</span>
                  </div>
                )}

                {/* Settlement address info */}
                {settlementAddress && (
                  <div style={{
                    marginTop: 12,
                    padding: '10px 12px',
                    background: 'rgba(245, 158, 11, 0.08)',
                    border: '1px solid rgba(245, 158, 11, 0.2)',
                    borderRadius: 8,
                    fontSize: 12,
                  }}>
                    <div style={{ color: '#F59E0B', fontWeight: 600, marginBottom: 4 }}>Step 1: Send USDC to settlement wallet</div>
                    <div style={{ fontFamily: 'DM Mono, monospace', fontSize: 11, color: 'var(--text-secondary)', wordBreak: 'break-all' }}>
                      {settlementAddress}
                    </div>
                    <button
                      className="chip-btn"
                      onClick={() => navigator.clipboard?.writeText(settlementAddress)}
                      style={{ fontSize: 10, padding: '2px 8px', marginTop: 6 }}
                    >
                      Copy Address
                    </button>
                  </div>
                )}

                {/* Phone */}
                <div style={{ marginTop: 12 }}>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>M-Pesa Phone Number</div>
                  <div className="modal-input-wrap">
                    <input
                      className="modal-input"
                      type="tel"
                      placeholder="+254 7XX XXX XXX"
                      value={phone}
                      onChange={e => setPhone(e.target.value)}
                    />
                  </div>
                </div>

                {/* Transaction Hash */}
                <div style={{ marginTop: 8 }}>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>Transaction Hash (proof of crypto transfer)</div>
                  <div className="modal-input-wrap">
                    <input
                      className="modal-input"
                      type="text"
                      placeholder="0x..."
                      value={txHash}
                      onChange={e => setTxHash(e.target.value)}
                    />
                  </div>
                </div>

                {txError && (
                  <div style={{ color: 'var(--red)', fontSize: 12, marginTop: 8, textAlign: 'center' }}>{txError}</div>
                )}

                <button
                  className="modal-cta"
                  onClick={handleWithdraw}
                  disabled={txLoading || !amount || !phone.trim() || !txHash.trim()}
                  style={{ width: '100%', marginTop: 12 }}
                >
                  {txLoading ? 'Processing...' : `Withdraw $${Number(amount || 0).toFixed(2)} USDC`}
                </button>
              </div>
            </div>
          )}

          {/* ── History Tab ── */}
          {!activeTx && tab === 'history' && (
            <div className="fu d3">
              {historyLoading ? (
                <div className="empty"><div className="empty-icon">&#8987;</div></div>
              ) : transactions.length === 0 ? (
                <div className="empty">
                  <div className="empty-icon">&#9671;</div>
                  <div className="empty-text">No transactions yet</div>
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {transactions.map(tx => (
                    <div
                      key={tx.transaction_id}
                      style={{
                        background: 'var(--glass-bg)',
                        border: '1px solid var(--glass-border)',
                        borderRadius: 'var(--rsm)',
                        padding: '12px 14px',
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                      }}
                    >
                      <div>
                        <div style={{ fontSize: 13, fontWeight: 600 }}>
                          {tx.type === 'onramp' ? 'Deposit' : 'Withdraw'}
                          <span style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: 6, fontWeight: 400 }}>
                            {tx.mobile_network || 'M-Pesa'}
                          </span>
                        </div>
                        <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 2 }}>
                          {tx.type === 'onramp'
                            ? `KES ${Number(tx.amount_fiat || 0).toLocaleString()} -> $${Number(tx.amount_crypto || 0).toFixed(2)}`
                            : `$${Number(tx.amount_crypto || 0).toFixed(2)} -> KES ${Number(tx.amount_fiat || 0).toLocaleString()}`}
                        </div>
                        <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>
                          {tx.created_at ? new Date(tx.created_at).toLocaleDateString() : ''}
                        </div>
                      </div>
                      <div style={{
                        fontSize: 11,
                        fontFamily: 'DM Mono, monospace',
                        color: STATUS_COLOR(tx.status),
                        fontWeight: 600,
                        textTransform: 'uppercase',
                      }}>
                        {tx.status}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* ── Info footer ── */}
          <div className="fu d8" style={{
            fontSize: 11,
            color: 'var(--text-muted)',
            textAlign: 'center',
            padding: '16px 12px 24px',
            lineHeight: 1.5,
          }}>
            Powered by Pretium. Deposits & withdrawals via M-Pesa.
            <br />
            {tab === 'deposit' ? 'KES is converted to USDC for trading.' : 'USDC is converted to KES and sent to your M-Pesa.'}
          </div>
        </div>

        <Navbar active="wallet" />
      </div>
    </AuthGate>
  );
}
