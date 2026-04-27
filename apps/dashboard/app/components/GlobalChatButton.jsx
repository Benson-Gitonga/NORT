'use client';
// P-GlobalChatButton: Floating chat FAB + general-purpose chat panel.
// Opens from any page via layout.jsx. Not tied to any market/signal.
// Sits at bottom-right, above the mobile nav and mode pill.

import { useState, useRef, useEffect } from 'react';
import { useAuth } from '@/hooks/useAuth';

// P-PLACEHOLDER MESSAGE: Replace this static reply with a real API call once
// the backend intern ships POST /agent/chat. See intern TODO list below.
const INIT_MSG = {
  id: 'init',
  role: 'ai',
  text: "Hey — I'm NORTBOT. Ask me anything about NORT, markets, or trading.",
};

export default function GlobalChatButton() {
  const { isAuthed, walletAddress } = useAuth();
  const [open, setOpen]         = useState(false);

  // Listen for external "open-nortbot" events (e.g. from ASK NORT BOT button)
  useEffect(() => {
    const handler = () => setOpen(true);
    window.addEventListener('open-nortbot', handler);
    return () => window.removeEventListener('open-nortbot', handler);
  }, []);
  const [messages, setMessages] = useState([INIT_MSG]);
  const [input, setInput]       = useState('');
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
      // P-API CALL: Replace this stub with sendChat(q) from api.js once
      // the backend intern ships POST /agent/chat. The function should live
      // in api.js and return { reply: string }. Example shape:
      //   const { reply } = await sendChat(q);
      //   addMsg('ai', reply);
      await new Promise(r => setTimeout(r, 900)); // P-STUB DELAY: remove when real endpoint is live
      addMsg('ai', "I'm not connected to the backend yet — ask a backend intern to ship POST /agent/chat.");
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
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          : /* chat bubble icon */
            <svg viewBox="0 0 24 24" width="22" height="22" stroke="currentColor" fill="none" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/>
            </svg>
        }
      </button>


      {/* P-CHAT PANEL: Slides up from the FAB when open */}
      {open && (
        <div className="gchat-panel">
          <div className="chat-header">
            <div className="chat-title">
              NORTBOT
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
                <span className="td"/><span className="td"/><span className="td"/>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          <div className="chat-input-row">
            <input
              className="chat-input"
              placeholder="Ask anything..."
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
