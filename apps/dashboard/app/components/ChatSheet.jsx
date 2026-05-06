'use client';
import { useState, useRef, useEffect } from 'react';
import { getAdvice, getPremiumAdvice, verifyPayment } from '@/lib/api';
import { useTelegram } from '@/hooks/useTelegram';
import { useAuth } from '@/hooks/useAuth';
import { useTier } from '@/hooks/useTier';
import LoginPrompt from './LoginPrompt';
import PremiumGate from './PremiumGate';

const INIT_MSG = {
  id: 'init',
  role: 'ai',
  text: 'Hey — I\'m NORTBOT. Ask me anything about this market.',
};

export default function ChatSheet({ signal, onClose }) {
  const { haptic } = useTelegram();
  const { isAuthed, walletAddress, login } = useAuth();
  const { tier, atLimit, usedToday, remaining, windowResetAt, refresh: refreshTier, FREE_DAILY_LIMIT } = useTier();

  const [messages, setMessages]     = useState([INIT_MSG]);
  const [input, setInput]           = useState('');
  const [thinking, setThinking]     = useState(false);
  const [showPremiumGate, setShowPremiumGate] = useState(false);
  const [lang, setLang]             = useState('en');  // visible toggle: 'en' | 'sw'
  const bottomRef = useRef(null);

  const isPremium = tier === 'premium';

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, thinking]);

  if (!isAuthed || !walletAddress) {
    return <LoginPrompt onLogin={login} onClose={onClose} message="Connect your wallet to chat with AI" />;
  }

  const addMsg = (role, text) => {
    setMessages(prev => [...prev, { id: Date.now(), role, text }]);
  };

  const formatAdvice = (resp) => {
    if (isPremium) {
      const risks = (resp.risks || []).map(r => `• ${r}`).join('\n');
      return `${resp.summary}\n\nWHY IT'S TRENDING\n${resp.why}\n\nRISKS\n${risks}\n\nVERDICT: ${resp.plan}\nConfidence: ${Math.round((resp.confidence || 0) * 100)}%\n\n${resp.disclaimer}`;
    }
    return `${resp.summary}\n\nVERDICT: ${resp.plan}\nConfidence: ${Math.round((resp.confidence || 0) * 100)}%\n\n${resp.disclaimer}`;
  };

  const send = async () => {
    const q = input.trim();
    if (!q || thinking) return;

    // Check limit before calling — show inline message in chat
    if (atLimit) {
      addMsg('user', q);
      setInput('');
      addMsg('ai',
        windowResetAt
          ? `You've used all ${FREE_DAILY_LIMIT} free calls this window. Your limit refreshes at ${windowResetAt}.\n\nUpgrade to Premium for unlimited access.`
          : `You've used all ${FREE_DAILY_LIMIT} free calls this window. Come back later or upgrade to Premium for unlimited access.`
      );
      return;
    }

    haptic.light();
    setInput('');
    addMsg('user', q);
    setThinking(true);
    try {
      const resp = isPremium
        ? await getPremiumAdvice(signal?.id, q, lang)
        : await getAdvice(signal?.id, q, lang);
      addMsg('ai', formatAdvice(resp));
      refreshTier(); // update usage counter
    } catch (err) {
      const msg = err?.message || '';
      if (msg.includes('402') || msg === 'PAYMENT_REQUIRED') {
        setShowPremiumGate(true);
      } else if (msg.includes('429')) {
        // Rate limit hit — show inline message in chat, not the paywall
        const resetMatch = msg.match(/refresh at (.+?)\./);
        const resetTime = resetMatch ? resetMatch[1] : null;
        addMsg('ai',
          resetTime
            ? `You've used all ${FREE_DAILY_LIMIT} free calls this window. Your limit refreshes at ${resetTime}.\n\nUpgrade to Premium for unlimited access.`
            : `You've used all ${FREE_DAILY_LIMIT} free calls this window. Come back later or upgrade to Premium for unlimited access.`
        );
        refreshTier();
      } else {
        addMsg('ai', 'Something went wrong. Try again.');
      }
    } finally {
      setThinking(false);
    }
  };

  return (
    <>
      <div className="modal-overlay" onClick={onClose}>
        <div className="chat-sheet" onClick={(e) => e.stopPropagation()}>
          <div className="chat-header">
            <div className="chat-title">
              NORTBOT
              <span className="chat-badge" style={{ color: isPremium ? '#F59E0B' : undefined }}>
                {isPremium ? '⚡ PREMIUM' : 'FREE'}
              </span>
            </div>
            {!isPremium && !atLimit && (
              <span style={{ fontSize: 11, color: 'var(--muted)', fontFamily: 'DM Mono, monospace', marginLeft: 'auto', marginRight: 10 }}>
                {remaining}/{FREE_DAILY_LIMIT} left
              </span>
            )}
            {/* Language toggle — visible to all users */}
            <button
              onClick={() => setLang(l => l === 'en' ? 'sw' : 'en')}
              title={lang === 'sw' ? 'Switch to English' : 'Badilisha kwa Kiswahili'}
              style={{
                fontSize: 10, padding: '2px 6px', marginRight: 6,
                background: lang === 'sw' ? 'rgba(16,185,129,0.15)' : 'rgba(255,255,255,0.06)',
                border: lang === 'sw' ? '1px solid rgba(16,185,129,0.4)' : '1px solid var(--border)',
                borderRadius: 4, color: lang === 'sw' ? '#10B981' : 'var(--muted)',
                cursor: 'pointer', fontFamily: 'DM Mono, monospace', lineHeight: 1.6,
              }}
            >
              {lang === 'sw' ? '🇰🇪 SW' : '🇬🇧 EN'}
            </button>
            <button className="chat-close" onClick={onClose}>✕</button>
          </div>

          <div className="chat-messages">
            {messages.map(m => (
              <div key={m.id} className={`msg ${m.role}`} style={{ whiteSpace: 'pre-line' }}>
                {m.text}
              </div>
            ))}

            {thinking && (
              <div className="msg-thinking">
                <span className="td" /><span className="td" /><span className="td" />
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Limit banner */}
          {atLimit && !isPremium && (
            <div
              onClick={() => setShowPremiumGate(true)}
              style={{
                padding: '10px 16px', background: 'rgba(245,158,11,0.1)',
                borderTop: '1px solid rgba(245,158,11,0.2)',
                fontSize: 12, color: '#F59E0B', cursor: 'pointer',
                fontFamily: 'DM Mono, monospace', textAlign: 'center',
              }}
            >
              Limit reached · Tap to upgrade →
            </div>
          )}

          {!atLimit && (
            <div className="chat-input-row">
              <input
                className="chat-input"
                placeholder={isPremium ? 'Ask anything — deep analysis mode...' : 'Ask about this market...'}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && send()}
                disabled={thinking}
              />
              <button
                className="chat-send"
                onClick={send}
                disabled={!input.trim() || thinking}
              >↑</button>
            </div>
          )}
        </div>
      </div>

      <PremiumGate
        open={showPremiumGate}
        onClose={() => { setShowPremiumGate(false); refreshTier(); }}
        reason={atLimit ? 'limit' : 'feature'}
        used={usedToday}
        limit={FREE_DAILY_LIMIT}
      />
    </>
  );
}
