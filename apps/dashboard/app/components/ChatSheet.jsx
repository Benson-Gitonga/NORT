'use client';
import { useState, useRef, useEffect } from 'react';
import { getAdvice, getPremiumAdvice, verifyPayment, getChatHistory } from '@/lib/api';
import { useTelegram } from '@/hooks/useTelegram';
import { useAuth } from '@/hooks/useAuth';
import { useTier } from '@/hooks/useTier';
import LoginPrompt from './LoginPrompt';

const INIT_MSG = {
  id: 'init',
  role: 'ai',
  text: "Hey — I'm NORT- AI advisor. Ask me anything about this market.",
};

export default function ChatSheet({ signal, onClose }) {
  const { haptic } = useTelegram();
  const { isAuthed, walletAddress, login } = useAuth();
  const { tier, remaining, atLimit, refresh, FREE_DAILY_LIMIT } = useTier();

  const [messages, setMessages] = useState([INIT_MSG]);
  const [input, setInput] = useState('');
  const [thinking, setThinking] = useState(false);
  const [gated, setGated] = useState(false);
  const [payInput, setPayInput] = useState('');
  const [payLoading, setPayLoading] = useState(false);
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, thinking]);

  // Load chat history from the backend when the sheet opens for this market
  useEffect(() => {
    if (!signal?.id || !isAuthed) return;
    getChatHistory(signal.id).then(history => {
      if (history && history.length > 0) {
        setMessages([INIT_MSG, ...history.map(m => {
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
    }).catch(() => {/* non-fatal — silently ignore */});
  }, [signal?.id, isAuthed]);

  if (!isAuthed || !walletAddress) {
    return <LoginPrompt onLogin={login} onClose={onClose} message="Connect your wallet to chat with AI" />;
  }

  const addMsg = (role, text) =>
    setMessages(prev => [...prev, { id: Date.now() + Math.random(), role, text }]);

  const formatAdvice = (resp) => {
    const planEmoji = { 'BUY YES': '🟢', 'BUY NO': '🔴', 'WAIT': '⏸️' }[resp.plan] || '';
    const confPct = Math.round((resp.confidence || 0) * 100);
    const auto = resp.auto_trade_result;

    let autoNote = '';
    if (auto?.executed) autoNote = `\n\n⚡ Auto-trade fired: ${auto.reason}`;
    else if (auto?.mode === 'confirm') autoNote = `\n\n⏳ Confirmation needed: ${auto.reason}`;
    else if (auto?.reason) autoNote = `\n\n◌ ${auto.reason}`;

    const stale = resp.stale_data_warning ? `\n\n⚠️ ${resp.stale_data_warning}` : '';

    // If the backend already returned deep-dive fields (e.g. because the user has a
    // confirmed payment and the auto-upgrade fired), show them regardless of whether
    // the local tier state has caught up yet.
    const hasDeepData = resp.why && resp.risks && resp.risks.length > 0;

    if (tier === 'free' && !hasDeepData) {
      return (
        `${resp.summary}\n\n` +
        `🔒 Unlock Premium to see full deep-dive (why it's trending, risks, and exact position targets).\n\n` +
        `${planEmoji} Plan: ${resp.plan} · Confidence: ${confPct}%` +
        autoNote + stale
      );
    }

    return (
      `${resp.summary}\n\n` +
      `Why trending: ${resp.why}\n\n` +
      `Risks: ${(resp.risks || []).join(' · ')}\n\n` +
      `${planEmoji} Plan: ${resp.plan} · Confidence: ${confPct}%` +
      autoNote + stale
    );
  };

  const send = async () => {
    const q = input.trim();
    if (!q || thinking) return;

    // Hard wall: free user at limit
    if (atLimit && tier === 'free') {
      haptic.error?.();
      addMsg('ai',
        `⚠️ You've used all ${FREE_DAILY_LIMIT} free advice calls for today.\n\n` +
        `Unlock Premium for unlimited advice, full analysis, and exact entry/exit targets.`
      );
      setGated(true);
      refresh(); // sync the counter so the bar reflects the true used count
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
      refresh(); // update the usage counter after a successful call
    } catch (err) {
      if (err.message === 'PAYMENT_REQUIRED') {
        setGated(true);
        addMsg('ai', '🔒 This market requires a Premium unlock. Use the payment form below.');
      } else if (err.message?.includes('429') || err.message?.includes('Limit')) {
        setGated(true);
        addMsg('ai',
          `⚠️ Daily free limit reached (${FREE_DAILY_LIMIT}/day).\n\nPaste your x402 payment proof below to unlock Premium.`
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
        addMsg('ai', '✅ Payment confirmed — Premium advice unlocked!');
        const premium = await getPremiumAdvice(signal?.id);
        addMsg('ai', formatAdvice(premium));
        refresh();
      } else {
        haptic.error?.();
        addMsg('ai', `❌ Payment invalid: ${result.error}`);
      }
    } catch {
      addMsg('ai', 'Verification failed. Try again.');
    } finally {
      setPayLoading(false);
      setPayInput('');
    }
  };

  // Tier badge label + colour
  const tierLabel = tier === 'premium' ? 'PREMIUM' : 'FREE';
  const tierColor = tier === 'premium' ? '#F59E0B' : 'var(--teal)';
  const usageLabel = tier === 'free'
    ? `${remaining ?? '?'} / ${FREE_DAILY_LIMIT} left today`
    : 'Unlimited';

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="chat-sheet" onClick={e => e.stopPropagation()}>

        {/* ── Header ── */}
        <div className="chat-header">
          <div className="chat-title">
            <span className="ai-dot" />
            NORT- AI advisor
            <span className="chat-badge" style={{ background: tierColor, color: '#000' }}>
              {tierLabel}
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {tier === 'free' && (
              <span style={{ fontSize: 10, color: atLimit ? 'var(--red)' : 'var(--muted)', fontFamily: 'DM Mono,monospace' }}>
                {atLimit ? '⛔ limit reached' : usageLabel}
              </span>
            )}
            <button className="chat-close" onClick={onClose}>✕</button>
          </div>
        </div>

        {/* ── Free tier usage bar ── */}
        {tier === 'free' && (
          <div style={{ padding: '4px 16px 0', display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{ flex: 1, height: 3, background: 'var(--g1)', borderRadius: 2, overflow: 'hidden' }}>
              <div style={{
                height: '100%',
                width: `${Math.min(100, ((FREE_DAILY_LIMIT - (remaining ?? FREE_DAILY_LIMIT)) / FREE_DAILY_LIMIT) * 100)}%`,
                background: atLimit ? 'var(--red)' : 'var(--teal)',
                transition: 'width 0.4s',
                borderRadius: 2,
              }} />
            </div>
            <span style={{ fontSize: 9, color: 'var(--muted)', fontFamily: 'DM Mono,monospace', whiteSpace: 'nowrap' }}>
              {atLimit ? 'LIMIT REACHED' : `${FREE_DAILY_LIMIT - (remaining ?? FREE_DAILY_LIMIT)}/${FREE_DAILY_LIMIT} used`}
            </span>
          </div>
        )}

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
                <strong>💳 How to unlock Premium:</strong><br />
                Send <strong>0.10 USDC</strong> to the NORT treasury on <strong>Base chain</strong>,
                then paste your transaction hash below.<br />
                <span style={{ color: 'var(--teal)', fontSize: 11 }}>
                  🧪 Type <strong>"demo"</strong> to try Premium free (dev mode)
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

        {/* ── Input row (hidden at limit for free users) ── */}
        {!gated && (
          <div className="chat-input-row">
            <input
              className="chat-input"
              placeholder={atLimit ? '⛔ Daily limit reached — unlock Premium' : 'Ask about this market...'}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && send()}
              disabled={thinking}
              style={atLimit ? { opacity: 0.5 } : {}}
            />
            <button
              className="chat-send"
              onClick={atLimit ? () => setGated(true) : send}
              disabled={thinking || (!atLimit && !input.trim())}
              style={atLimit ? { background: 'var(--red)', opacity: 0.8 } : {}}
            >
              {atLimit ? '🔒' : '↑'}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
