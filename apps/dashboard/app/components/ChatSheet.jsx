'use client';
import { useState, useRef, useEffect } from 'react';
import { getAdvice, getPremiumAdvice, verifyPayment, getChatHistory } from '@/lib/api';
import { useTelegram } from '@/hooks/useTelegram';
import { useAuth } from '@/hooks/useAuth';
import { useTier } from '@/hooks/useTier';
import LoginPrompt from './LoginPrompt';


export default function ChatSheet({ signal, onClose }) {
  const { haptic } = useTelegram();
  const { isAuthed, walletAddress, login } = useAuth();
  const { tier, atLimit, windowResetAt, refresh, optimisticUpgrade } = useTier();

  const buildInitMsg = (t) => ({
    id: 'init',
    role: 'ai',
    text: t === 'premium'
      ? "Welcome back — full analysis mode is active. Ask me anything about this market and I'll give you exact entry/exit targets and position sizing."
      : "Hey — I'm NORT, your AI market advisor. Ask me anything about this market.",
  });

  const [messages, setMessages] = useState([buildInitMsg(tier)]);
  const [input, setInput] = useState('');
  const [thinking, setThinking] = useState(false);
  const [gated, setGated] = useState(false);
  const [payInput, setPayInput] = useState('');
  const [payLoading, setPayLoading] = useState(false);
  const bottomRef = useRef(null);

  // Update greeting once tier resolves from loading state
  useEffect(() => {
    setMessages(prev => {
      if (prev.length === 1 && prev[0].id === 'init') {
        return [buildInitMsg(tier)];
      }
      return prev;
    });
  }, [tier]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, thinking]);

  // Load chat history from the backend when the sheet opens for this market
  useEffect(() => {
    if (!signal?.id || !isAuthed) return;
    getChatHistory(signal.id).then(history => {
      if (history && history.length > 0) {
        setMessages([buildInitMsg(tier), ...history.map(m => {
          if (m.role === 'ai' && m.advice) {
            return {
              id: m.id,
              role: 'ai',
              text: formatAdvice({
                plan: m.advice.suggested_plan,
                confidence: m.advice.confidence,
                auto_trade_result: m.advice.auto_trade_result,
                summary: m.advice.summary,
                why: m.advice.why_trending,
                risks: m.advice.risk_factors,
                stale_data_warning: m.advice.stale_data_warning
              })
            };
          }
          return { id: m.id, role: m.role, text: m.text };
        })]);
      }
    }).catch(() => {/* non-fatal — silently ignore */ });
  }, [signal?.id, isAuthed]);

  if (!isAuthed || !walletAddress) {
    return <LoginPrompt onLogin={login} onClose={onClose} message="Connect your wallet to chat with AI" />;
  }

  const addMsg = (role, text) =>
    setMessages(prev => [...prev, { id: Date.now() + Math.random(), role, text }]);

  const formatAdvice = (resp) => {
    // resp shape: { summary, why, risks, plan, confidence, auto_trade_result, stale_data_warning }
    const planLabel = resp.plan || 'WAIT';
    const confPct = Math.round((resp.confidence || 0) * 100);
    const auto = resp.auto_trade_result;

    let autoNote = '';
    if (auto?.executed) autoNote = `\n\nAuto-trade fired: ${auto.reason}`;
    else if (auto?.mode === 'confirm') autoNote = `\n\nConfirmation needed: ${auto.reason}`;
    else if (auto?.reason && auto.reason !== 'Auto-trade is disabled') autoNote = `\n\n${auto.reason}`;

    const stale = resp.stale_data_warning ? `\n\n${resp.stale_data_warning}` : '';

    // Premium response: has full why + risks data
    const hasPremiumData = resp.why && resp.risks && resp.risks.length > 0;

    if (hasPremiumData) {
      const risksLines = resp.risks.map(r => `- ${r}`).join('\n');
      return (
        `${resp.summary}\n\n` +
        `WHY IT'S TRENDING\n${resp.why}\n\n` +
        `KEY RISKS\n${risksLines}\n\n` +
        `VERDICT: ${planLabel}\nConfidence: ${confPct}%` +
        autoNote + stale
      );
    }

    // Free response: summary + verdict only
    return (
      `${resp.summary}\n\n` +
      `VERDICT: ${planLabel}\nConfidence: ${confPct}%` +
      autoNote + stale
    );
  };

  const send = async () => {
    const q = input.trim();
    if (!q || thinking) return;

    // Hard wall: free user at limit
    if (atLimit && tier === 'free') {
      haptic.error?.();
      setGated(true);
      refresh();
      return;
    }

    haptic.light?.();
    setInput('');
    addMsg('user', q);
    setThinking(true);

    try {
      let resp;
      if (tier === 'premium' || gated) {
        resp = await getPremiumAdvice(signal?.id, q);
      } else {
        resp = await getAdvice(signal?.id, q);
      }
      addMsg('ai', formatAdvice(resp));
      try {
        localStorage.removeItem('nort_tier');
        localStorage.removeItem('nort_at_limit');
        localStorage.removeItem('nort_reset_at');
        localStorage.removeItem('nort_used');
      } catch {}
      refresh(); // update the usage counter after a successful call
    } catch (err) {
      if (err.message === 'PAYMENT_REQUIRED') {
        setGated(true);
        addMsg('ai', 'This market requires a Premium unlock. Use the payment form below.');
      } else if (err.message?.includes('429') || err.message?.includes('Limit') || err.message?.includes('free messages')) {
        setGated(true);
        addMsg('ai',
          err.detail || err.message ||
          'Your free messages are used up. Upgrade to Premium for unlimited access.'
        );
      } else {
        addMsg('ai', 'Something went wrong. Try again in a moment.');
      }
    } finally {
      setThinking(false);
    }
  };

  const handlePay = async () => {
    const proof = payInput.trim();
    if (!proof) return;
    haptic.medium?.();
    setPayLoading(true);
    try {
      const result = await verifyPayment(proof, signal?.id);
      if (result.valid) {
        haptic.success?.();
        setGated(false);
        addMsg('ai', 'Payment confirmed — Premium advice unlocked!');
        // Flip tier badge instantly, then load premium advice
        optimisticUpgrade();
        const premium = await getPremiumAdvice(signal?.id);
        addMsg('ai', formatAdvice(premium));
      } else {
        haptic.error?.();
        addMsg('ai', `Payment invalid: ${result.error}`);
      }
    } catch {
      addMsg('ai', 'Verification failed. Try again.');
    } finally {
      setPayLoading(false);
      setPayInput('');
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="chat-sheet" onClick={e => e.stopPropagation()}>

        {/* ── Header ── */}
        <div className="chat-header">
          <div className="chat-title">
            <span className="ai-dot" />
            NORT- AI advisor
            <span className="chat-badge" style={{ background: tier === 'premium' ? '#F59E0B' : 'var(--teal)', color: '#000' }}>
              {tier === 'premium' ? 'PREMIUM' : 'FREE'}
            </span>
          </div>
          <button className="chat-close" onClick={onClose}>✕</button>
        </div>

        {/* ── Messages ── */}
        <div className="chat-messages">
          {messages.map(m => (
            <div key={m.id} className={`msg ${m.role}`} style={{ whiteSpace: 'pre-line' }}>
              {m.text}
            </div>
          ))}

          {/* Premium gate (payment proof form) */}
          {gated && (
            <div className="premium-gate">
              <div className="gate-label">PREMIUM · 0.10 USDC</div>
              <div style={{ fontSize: 12, color: 'var(--g4)', lineHeight: 1.6, marginBottom: 8 }}>
                <strong>How to unlock Premium:</strong><br />
                Send <strong>0.10 USDC</strong> to the NORT treasury on <strong>Base chain</strong>,
                then paste your transaction hash below.<br />
                <span style={{ color: 'var(--teal)', fontSize: 11 }}>
                  Type <strong>"demo"</strong> to try Premium free (dev mode)
                </span>
              </div>
              <input
                className="chat-input"
                style={{ borderRadius: 'var(--rsm)', width: '100%' }}
                placeholder="Paste tx hash or type 'demo'..."
                value={payInput}
                onChange={e => setPayInput(e.target.value)}
              />
              <button className="gate-btn" onClick={handlePay} disabled={payLoading}>
                {payLoading ? 'Verifying...' : 'Unlock Premium →'}
              </button>
            </div>
          )}

          {thinking && (
            <div className="msg-thinking">
              <span className="td" /><span className="td" /><span className="td" />
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* ── Input row — fully locked when free user is at limit ── */}
        {!gated && (
          <div className="chat-input-row">
            {atLimit ? (
              <div style={{
                flex: 1, padding: '10px 14px', borderRadius: 'var(--rsm)',
                background: 'var(--g1)', border: '1px solid var(--red)',
                color: 'var(--red)', fontSize: 12, lineHeight: 1.5, textAlign: 'center',
              }}>
                Out of free messages
                {windowResetAt && <><br /><span style={{ color: 'var(--muted)', fontSize: 11 }}>Your limit will refresh at {windowResetAt}</span></>}
                <br />
                <button
                  style={{ marginTop: 6, fontSize: 11, color: 'var(--teal)', background: 'none', border: 'none', cursor: 'pointer', textDecoration: 'underline' }}
                  onClick={() => setGated(true)}
                >
                  Unlock Premium →
                </button>
              </div>
            ) : (
              <>
                <input
                  className="chat-input"
                  placeholder="Ask about this market..."
                  value={input}
                  onChange={e => setInput(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && send()}
                  disabled={thinking}
                />
                <button className="chat-send" onClick={send} disabled={thinking || !input.trim()}>↑</button>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
