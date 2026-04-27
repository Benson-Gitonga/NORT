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
  const { tier, atLimit, usedToday, remaining, refresh: refreshTier, FREE_DAILY_LIMIT } = useTier();
  const isPremium = tier === 'premium';

  const [open, setOpen]             = useState(false);
  const [messages, setMessages]     = useState([INIT_MSG]);
  const [input, setInput]           = useState('');
  const [thinking, setThinking]     = useState(false);
  const [showPremiumGate, setShowPremiumGate] = useState(false);
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

    // Free users: only /advice <market_id> allowed — block general chat
    if (!isPremium && !isAdviceCmd(q)) {
      setShowPremiumGate(true);
      return;
    }

    // Block if at limit
    if (atLimit) {
      setShowPremiumGate(true);
      return;
    }

    setInput('');
    addMsg('user', q);
    setThinking(true);
    try {
      const { reply } = await sendChat(q, 'en', walletAddress || null);
      addMsg('ai', reply);
      refreshTier();
    } catch (err) {
      const msg = err?.message || '';
      if (msg.includes('429')) {
        setShowPremiumGate(true);
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
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          : <svg viewBox="0 0 24 24" width="22" height="22" stroke="currentColor" fill="none" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/>
            </svg>
        }
      </button>

      {open && (
        <div className="gchat-panel">
          <div className="chat-header">
            <div className="chat-title">
              NORTBOT
              <span className="chat-badge" style={{ color: isPremium ? '#F59E0B' : undefined }}>
                {isPremium ? '⚡ PREMIUM' : 'GLOBAL'}
              </span>
            </div>
            {!isPremium && !atLimit && (
              <span style={{ fontSize: 11, color: 'var(--muted)', fontFamily: 'DM Mono, monospace', marginLeft: 'auto', marginRight: 10 }}>
                {remaining}/{FREE_DAILY_LIMIT} left
              </span>
            )}
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
                <span className="td"/><span className="td"/><span className="td"/>
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
              {!isPremium && (
                <div style={{ padding: '6px 16px 2px', fontSize: 10, color: 'var(--muted)', fontFamily: 'DM Mono, monospace' }}>
                  Free: <span style={{ color: '#F59E0B' }}>/advice &lt;market-id&gt;</span> · General chat is ⚡ Premium
                </div>
              )}
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
