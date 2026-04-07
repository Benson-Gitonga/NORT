'use client';
import { useState, useRef, useEffect } from 'react';
import { sendChat } from '@/lib/api';
import { useAuth } from '@/hooks/useAuth';

const INIT_MSG = {
  id: 'init',
  role: 'ai',
  text: "Hey — I'm NORT Bot 🤖\n\nAsk me anything about NORT, markets, or trading.\n\nTip: Type /advice <market_id> to get full AI analysis on any market.",
};

export default function GlobalChatButton() {
  const { isAuthed, walletAddress } = useAuth();
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([INIT_MSG]);
  const [input, setInput] = useState('');
  const [thinking, setThinking] = useState(false);
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, thinking]);

  const addMsg = (role, text) =>
    setMessages(prev => [...prev, { id: Date.now() + Math.random(), role, text }]);


  const send = async () => {
    const q = input.trim();
    if (!q || thinking) return;
    setInput('');
    addMsg('user', q);
    setThinking(true);
    try {
      const { reply } = await sendChat(q, 'en', walletAddress || null);
      addMsg('ai', reply);
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new Event('nort-tier-refresh'));
      }
    } catch {
      addMsg('ai', 'Something went wrong. Try again.');
    } finally {
      setThinking(false);
    }
  };

  return (
    <>
      {/* P-FAB BUTTON: Floating action button, bottom-right, above mobile nav */}
      <button
        className="gchat-fab"
        onClick={() => setOpen(o => !o)}
        aria-label="Open AI chat"
      >
        {open
          ? /* close icon */
          <svg viewBox="0 0 24 24" width="22" height="22" stroke="currentColor" fill="none" strokeWidth="2" strokeLinecap="round">
            <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
          </svg>
          : /* chat bubble icon */
          <svg viewBox="0 0 24 24" width="22" height="22" stroke="currentColor" fill="none" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" />
          </svg>
        }
      </button>


      {/* P-CHAT PANEL: Slides up from the FAB when open */}
      {open && (
        <div className="gchat-panel">
          <div className="gchat-header">
            <div className="chat-title">
              <span className="ai-dot" />
              NORT Bot
              <span className="chat-badge">GLOBAL</span>
            </div>
            <button className="chat-close" onClick={() => setOpen(false)}>✕</button>
          </div>

          <div className="gchat-messages">
            {/* P-AUTH GATE: Show login nudge if wallet not connected */}
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

          <div className="chat-input-row">
            <input
              className="chat-input"
              placeholder="Ask anything or /advice <market_id>..."
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
          </div>
        </div>
      )}
    </>
  );
}
