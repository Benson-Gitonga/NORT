'use client';
import { useState, useRef, useEffect } from 'react';
import { useAuth } from '@/hooks/useAuth';
import { useTier } from '@/hooks/useTier';
import { sendChat } from '@/lib/api';
import PremiumGate from './PremiumGate';

const INIT_MSG = {
  id: 'init',
  role: 'ai',
  text: "Hey — I'm NORTBOT. Ask me anything about NORT, markets, or trading.",
};

export default function GlobalChatButton() {
  const { isAuthed, walletAddress } = useAuth();
  const { tier, atLimit, usedToday, remaining, windowResetAt, refresh: refreshTier, FREE_DAILY_LIMIT } = useTier();
  const isPremium = tier === 'premium';

  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([INIT_MSG]);
  const [input, setInput] = useState('');
  const [thinking, setThinking] = useState(false);
  const [showPremiumGate, setShowPremiumGate] = useState(false);
  const [lang, setLang] = useState('en');  // visible toggle: 'en' | 'sw'
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, thinking]);

  const addMsg = (role, text) =>
    setMessages(prev => [...prev, { id: Date.now() + Math.random(), role, text }]);

  const isAdviceCmd = (text) => /^\/advice\s+\S+/i.test(text.trim());

  const send = async () => {
    const q = input.trim();
    if (!q || thinking) return;

    // Free users: only /advice <market_id> allowed — show inline message for general chat
    if (!isPremium && !isAdviceCmd(q)) {
      addMsg('user', q);
      setInput('');
      addMsg('ai', 'Free users can run market advice using:\n/advice <market-id>\n\nFor general chat, upgrade to Premium.');
      return;
    }

    // Block if at limit — show inline message
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

    setInput('');
    addMsg('user', q);
    setThinking(true);
    try {
      const { reply } = await sendChat(q, lang, walletAddress || null);
      addMsg('ai', reply);
      refreshTier();
    } catch (err) {
      const msg = err?.message || '';
      if (msg.includes('429')) {
        const resetMatch = msg.match(/refresh at (.+?)\./);
        const resetTime = resetMatch ? resetMatch[1] : null;
        addMsg('ai',
          resetTime
            ? `You've used all ${FREE_DAILY_LIMIT} free calls this window. Your limit refreshes at ${resetTime}.\n\nUpgrade to Premium for unlimited access.`
            : `You've used all ${FREE_DAILY_LIMIT} free calls this window. Come back later or upgrade to Premium for unlimited access.`
        );
        refreshTier();
      } else {
        addMsg('ai', 'Something went wrong. Try again in a moment.');
      }
    } finally {
      setThinking(false);
    }
  };

  return (
    <>
      <button
        className="gchat-fab"
        onClick={() => setOpen(o => !o)}
        aria-label="Open AI chat"
      >
        {open
          ? <svg viewBox="0 0 24 24" width="22" height="22" stroke="currentColor" fill="none" strokeWidth="2" strokeLinecap="round">
            <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
          </svg>
          : <svg viewBox="0 0 24 24" width="22" height="22" stroke="currentColor" fill="none" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" />
          </svg>
        }
      </button>

      {open && (
        <div className="gchat-panel" style={{
          border: isPremium ? '1px solid rgba(245,158,11,0.4)' : undefined,
          boxShadow: isPremium ? '0 0 0 1px rgba(245,158,11,0.15), 0 8px 32px rgba(0,0,0,0.5)' : undefined,
        }}>
          <div className="chat-header" style={{
            background: isPremium ? 'rgba(245,158,11,0.06)' : undefined,
            borderBottom: isPremium ? '1px solid rgba(245,158,11,0.2)' : undefined,
          }}>
            <div className="chat-title">
              NORTBOT
              <span className="chat-badge" style={{ color: isPremium ? '#F59E0B' : undefined }}>
                {isPremium ? 'PREMIUM' : 'GLOBAL'}
              </span>
            </div>
            {!isPremium && !atLimit && (
              <span style={{ fontSize: 11, color: 'var(--muted)', fontFamily: 'DM Mono, monospace', marginLeft: 'auto', marginRight: 6 }}>
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
            <button className="chat-close" onClick={() => setOpen(false)}>✕</button>
          </div>

          <div className="gchat-messages">
            {!isAuthed && (
              <div className="msg ai">Connect your wallet to get personalised advice.</div>
            )}
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

          {/* Bottom input area */}
          {atLimit ? (
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
          ) : (
            <div style={{ borderTop: '1px solid var(--border)' }}>
              <div className="chat-input-row">
                <input
                  className="chat-input"
                  placeholder={isPremium ? 'Ask anything...' : '/advice <market-id>'}
                  value={input}
                  onChange={e => setInput(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && send()}
                  disabled={thinking}
                />
                <button className="chat-send" onClick={send} disabled={!input.trim() || thinking}>↑</button>
              </div>
            </div>
          )}
        </div>
      )}

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
