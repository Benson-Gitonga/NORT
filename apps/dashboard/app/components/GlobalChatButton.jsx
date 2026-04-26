'use client';
import { useState, useRef, useEffect } from 'react';
import { sendChat } from '@/lib/api';
import { useAuth } from '@/hooks/useAuth';
import { useTier } from '@/hooks/useTier';

export default function GlobalChatButton() {
  const { isAuthed, walletAddress } = useAuth();
  const { atLimit, windowResetAt, refresh, tier } = useTier();
  const isPremium = tier === 'premium';

  const buildInitMsg = (premium) => ({
    id: 'init',
    role: 'ai',
    text: premium
      ? "Hey — I'm NORT Bot. You have full Premium chat access.\n\nAsk me anything about markets, trading strategy, or the platform. Use /advice <market_id> to pull a full deep-dive on any market."
      : "Hey — I'm NORT Bot.\n\nUse /advice <market_id> to get AI analysis on any market.\n\nUpgrade to Premium to unlock free-form chat.",
  });

  const [open, setOpen]         = useState(false);
  const [messages, setMessages] = useState([buildInitMsg(isPremium)]);
  const [input, setInput]       = useState('');
  const [thinking, setThinking] = useState(false);
  const bottomRef = useRef(null);

  // Re-build init message once tier resolves from loading state
  useEffect(() => {
    setMessages([buildInitMsg(isPremium)]);
  }, [isPremium]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, thinking]);

  const addMsg = (role, text) =>
    setMessages(prev => [...prev, { id: Date.now() + Math.random(), role, text }]);

  const send = async () => {
    const q = input.trim();
    if (!q || thinking) return;

    // Hard gate — free user at combined limit
    if (atLimit && !isPremium) {
      addMsg('ai',
        `You're out of free messages.` +
        (windowResetAt ? `\n\nYour limit refreshes at ${windowResetAt}.` : '') +
        `\n\nUpgrade to Premium for unlimited access.`
      );
      return;
    }

    // Soft gate — free user trying general chat (not /advice command)
    const isAdviceCmd = /^\/advice\s+\S+/i.test(q);
    if (!isPremium && !isAdviceCmd) {
      addMsg('ai',
        `General chat is a Premium feature.\n\n` +
        `You can still use /advice <market_id> to get AI analysis on any market — tap a signal card to find the market ID.\n\n` +
        `Upgrade to Premium to unlock free-form chat, deep-dive analysis, and exact entry/exit targets.`
      );
      return;
    }

    setInput('');
    addMsg('user', q);
    setThinking(true);
    try {
      const { reply } = await sendChat(q, 'en', walletAddress || null);
      addMsg('ai', reply);
      try {
        localStorage.removeItem('nort_tier');
        localStorage.removeItem('nort_at_limit');
        localStorage.removeItem('nort_reset_at');
        localStorage.removeItem('nort_used');
      } catch {}
      window.dispatchEvent(new Event('nort-tier-refresh'));
      refresh();
    } catch (err) {
      const msg = err?.message || '';
      if (msg.includes('429') || msg.toLowerCase().includes('limit')) {
        addMsg('ai', 'You\'ve hit your free message limit. Upgrade to Premium for unlimited access.');
      } else {
        addMsg('ai', 'Something went wrong. Try again.');
      }
    } finally {
      setThinking(false);
    }
  };

  return (
    <>
      {/* Floating action button */}
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

      {/* Chat panel */}
      {open && (
        <div className="gchat-panel">
          <div className="gchat-header">
            <div className="chat-title">
              <span className="ai-dot" />
              NORT Bot
              <span
                className="chat-badge"
                style={{
                  background: isPremium ? '#F59E0B' : 'var(--teal)',
                  color: '#000',
                }}
              >
                {isPremium ? 'PREMIUM' : 'FREE'}
              </span>
            </div>
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

          {/* Input row */}
          <div className="chat-input-row">
            {atLimit && !isPremium ? (
              <div style={{
                flex: 1, padding: '10px 12px', borderRadius: 'var(--rsm)',
                background: 'var(--g1)', border: '1px solid var(--red)',
                color: 'var(--red)', fontSize: 11, textAlign: 'center', lineHeight: 1.6,
              }}>
                Out of free messages
                {windowResetAt && (
                  <><br /><span style={{ color: 'var(--muted)' }}>Refreshes at {windowResetAt}</span></>
                )}
              </div>
            ) : (
              <>
                <input
                  className="chat-input"
                  placeholder={isPremium ? 'Ask anything...' : '/advice <market_id> or upgrade for chat...'}
                  value={input}
                  onChange={e => setInput(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && send()}
                  disabled={thinking}
                />
                <button
                  className="chat-send"
                  onClick={send}
                  disabled={!input.trim() || thinking}
                >↑</button>
              </>
            )}
          </div>
        </div>
      )}
    </>
  );
}

