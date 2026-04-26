'use client';
import { useState, useRef, useEffect } from 'react';
import { getAdvice, getPremiumAdvice, verifyPayment } from '@/lib/api';
import { useTelegram } from '@/hooks/useTelegram';
import { useAuth } from '@/hooks/useAuth';
import LoginPrompt from './LoginPrompt';

const INIT_MSG = {
  id: 'init',
  role: 'ai',
  text: 'Hey — I\'m NORTBOT. Ask me anything about this market.',
};

export default function ChatSheet({ signal, onClose }) {
  const { haptic } = useTelegram();
  const { isAuthed, walletAddress, login } = useAuth();
  const [messages, setMessages]     = useState([INIT_MSG]);
  const [input, setInput]           = useState('');
  const [thinking, setThinking]     = useState(false);
  const [gated, setGated]           = useState(signal?.locked || false);
  const [payInput, setPayInput]     = useState('');
  const [payLoading, setPayLoading] = useState(false);
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, thinking]);

  if (!isAuthed || !walletAddress) {
    return <LoginPrompt onLogin={login} onClose={onClose} message="Connect your wallet to chat with AI" />;
  }

  const addMsg = (role, text) => {
    setMessages(prev => [...prev, { id: Date.now(), role, text }]);
  };

  const formatAdvice = (resp) =>
    `${resp.summary}\n\n${resp.why}\n\nRisks: ${resp.risks.join(', ')}\n\nPlan: ${resp.plan}`;

  const send = async () => {
    const q = input.trim();
    if (!q || thinking) return;
    haptic.light();
    setInput('');
    addMsg('user', q);
    setThinking(true);
    try {
      const resp = signal?.locked ? await getPremiumAdvice(signal?.id) : await getAdvice(signal?.id, q);
      addMsg('ai', formatAdvice(resp));
    } catch {
      addMsg('ai', 'Something went wrong. Try again.');
    } finally {
      setThinking(false);
    }
  };

  const handlePay = async () => {
    const proof = payInput.trim();
    if (!proof) return;
    haptic.medium();
    setPayLoading(true);
    try {
      const result = await verifyPayment(proof, signal?.id);
      if (result.valid) {
        haptic.success();
        setGated(false);
        const premium = await getPremiumAdvice(signal?.id);
        addMsg('ai', 'Payment confirmed. Premium advice unlocked.');
        addMsg('ai', formatAdvice(premium));
      } else {
        haptic.error();
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
      <div className="chat-sheet" onClick={(e) => e.stopPropagation()}>
        <div className="chat-header">
          <div className="chat-title">
            NORTBOT
            <span className="chat-badge">{gated ? 'PREMIUM' : 'FREE'}</span>
          </div>
          <button className="chat-close" onClick={onClose}>✕</button>
        </div>

        <div className="chat-messages">
          {messages.map(m => (
            <div key={m.id} className={`msg ${m.role}`} style={{ whiteSpace: 'pre-line' }}>
              {m.text}
            </div>
          ))}

          {gated && (
            <div className="premium-gate">
              <div className="gate-label">PREMIUM · 0.10 USDC</div>
              <div style={{ fontSize: 12, color: 'var(--g4)', lineHeight: 1.4 }}>
                Paste your x402 payment proof to unlock full analysis.
              </div>
              <input
                className="chat-input"
                style={{ borderRadius: 'var(--rsm)', width: '100%' }}
                placeholder="Paste payment proof..."
                value={payInput}
                onChange={(e) => setPayInput(e.target.value)}
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

        {!gated && (
          <div className="chat-input-row">
            <input
              className="chat-input"
              placeholder="Ask about this market..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && send()}
              disabled={thinking}
            />
            <button className="chat-send" onClick={send} disabled={!input.trim() || thinking}>
              ↑
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
