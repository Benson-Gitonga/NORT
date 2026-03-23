'use client';
/**
 * NortBot.js
 * ─────────────────────────────────────────────
 * Section 5: "Chat with your NORT Bot"
 *
 * Layout: two-panel grid
 *   LEFT  — Spline 3D robot iframe (the animated N-Core V2 bot model)
 *   RIGHT — Live chat UI with pre-seeded messages, quick-chip buttons,
 *           and a working input that cycles through canned AI responses.
 *
 * Interactivity is pure client-side (no API calls).
 * The chat logic lives in the nortSend() function at the bottom.
 *
 * To swap the Spline model: replace the iframe `src` URL.
 * To add more bot responses: extend the `RESPONSES` object.
 * ─────────────────────────────────────────────
 */

import { useEffect, useRef, useState } from 'react';

/* ── Bot response map ─────────────────────────────────────────────────── */
const RESPONSES = {
  default: [
    "Scanning live markets… I see <strong style='color:#00e5b0'>12 active opportunities</strong> on Polymarket right now. Top pick: BTC $100k at 72¢ with 82% confidence.",
    "Based on current volume and momentum, I'd recommend <strong style='color:#f4f4f5'>BUY YES</strong> on ETH $5k. Liquidity is surging — 18% above 7-day avg. Confidence: <strong style='color:#00e5b0'>76%</strong>.",
    "My models show <strong style='color:#00e5b0'>3 HOT signals</strong> this hour: BTC $100k, ETH $5k, and the Rockets over/under. Want a deep dive on any?",
    "I'm tracking <strong style='color:#f4f4f5'>31 signals</strong> across Crypto and Sports. Win rate on HOT signals this week: <strong style='color:#00e5b0'>68%</strong>.",
  ],
  hot:    "🔥 Today's hottest signals:<br><br>• <strong style='color:#f4f4f5'>BTC $100k</strong> — 82% conf · BUY YES at 72¢<br>• <strong style='color:#f4f4f5'>ETH $5k</strong> — 76% conf · BUY YES at 58¢<br>• <strong style='color:#f4f4f5'>SOL $300</strong> — 71% conf · BUY YES at 64¢<br><br>All showing volume spikes above <strong style='color:#00e5b0'>3×</strong> avg.",
  eth:    "📊 <strong style='color:#f4f4f5'>Will ETH hit $5k?</strong><br><br>Current: 58¢ YES · $62.5K volume<br>Key drivers: ETF inflows +40%, whale accumulation, RSI oversold.<br><br>My call: <span style='color:#00e5b0;font-weight:700;'>BUY YES</span> · Confidence: <strong style='color:#00e5b0'>76%</strong>",
  rockets:"🏀 <strong style='color:#f4f4f5'>Rockets 52.5 wins?</strong><br><br>Current: 54¢ YES · $62.5K volume<br>They're 28-14 on pace. Key risk: injury concerns.<br><br>My call: <span style='color:#a1a1aa;font-weight:700;'>WAIT</span> — price is fairly valued.",
  picks:  "🎯 My top 3 picks right now:<br><br>1. <strong style='color:#f4f4f5'>BTC $100k</strong> · <span style='color:#00e5b0'>BUY YES</span> · 82% conf<br>2. <strong style='color:#f4f4f5'>ETH $5k</strong> · <span style='color:#00e5b0'>BUY YES</span> · 76% conf<br>3. <strong style='color:#f4f4f5'>SOL $300</strong> · <span style='color:#00e5b0'>BUY YES</span> · 71% conf",
};

/* ── Seed messages shown on first load ────────────────────────────────── */
const SEED_MESSAGES = [
  {
    from: 'bot',
    html: "Hey! I'm NORT Bot. I scan Polymarket 24/7 and surface high-probability trades for you. What would you like to know?",
    time: '10:41 AM',
  },
  {
    from: 'user',
    html: "What's the best signal right now?",
    time: '10:42 AM',
  },
  {
    from: 'bot',
    html: "🔥 <strong style='color:#f4f4f5'>Will BTC hit $100k?</strong> is the top signal — <span style='color:#00e5b0;font-weight:600;'>82% confidence</span>. Volume is 3× above average with strong whale accumulation. My call: <span style='color:#00e5b0;font-weight:700;'>BUY YES</span> at current 72¢.",
    time: '10:42 AM',
  },
];

/* ── Quick-action chips shown above the input ─────────────────────────── */
const CHIPS = [
  { label: "🔥 What's hot today?",  query: "What are the hottest signals today?" },
  { label: "Analyze ETH $5k",       query: "Analyze ETH $5k market"              },
  { label: "Rockets bet?",          query: "Should I bet on the Rockets?"         },
  { label: "Top 3 picks",           query: "Give me your top 3 picks"             },
];

/* ── Bot avatar SVG (brain icon) ─────────────────────────────────────── */
function BotAvatar({ size = 28 }) {
  return (
    <div style={{
      width: size, height: size, borderRadius: '50%', flexShrink: 0, marginTop: 2,
      background: 'linear-gradient(135deg,#00e5b0,#0090ff)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      boxShadow: '0 0 12px rgba(0,229,176,0.3)',
    }}>
      <svg width={size * 0.4} height={size * 0.4} viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 2a7 7 0 0 1 7 7c0 3-1.5 5-3.5 6.5V18a1 1 0 0 1-1 1h-5a1 1 0 0 1-1-1v-2.5C6.5 14 5 12 5 9a7 7 0 0 1 7-7z"/>
        <path d="M9 21h6"/>
      </svg>
    </div>
  );
}

/* ── Single chat bubble ───────────────────────────────────────────────── */
function ChatBubble({ msg }) {
  const isBot = msg.from === 'bot';
  return (
    <div className="chat-bubble-anim" style={{ display: 'flex', gap: 10, flexDirection: isBot ? 'row' : 'row-reverse' }}>

      {/* Avatar */}
      {isBot
        ? <BotAvatar size={28} />
        : <div style={{ width: 28, height: 28, borderRadius: '50%', background: '#27272a', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, marginTop: 2, fontSize: 10, fontWeight: 700, color: '#a1a1aa' }}>U</div>
      }

      {/* Bubble + timestamp */}
      <div style={{ maxWidth: '82%', display: 'flex', flexDirection: 'column', gap: 4, alignItems: isBot ? 'flex-start' : 'flex-end' }}>
        <div
          dangerouslySetInnerHTML={{ __html: msg.html }}
          style={{
            padding: '12px 16px',
            borderRadius: 16,
            borderTopLeftRadius: isBot ? 4 : 16,
            borderTopRightRadius: isBot ? 16 : 4,
            fontSize: 13, lineHeight: 1.6,
            background: isBot ? '#1a2535' : 'linear-gradient(135deg,#00b894,#0090ff)',
            border: isBot ? '1px solid rgba(255,255,255,0.05)' : '1px solid rgba(0,229,176,0.15)',
            color: isBot ? '#d4d4d8' : '#fff',
          }}
        />
        <span style={{ fontSize: 9, color: '#3f3f46', fontFamily: 'Space Grotesk, monospace', marginLeft: isBot ? 4 : 0, marginRight: isBot ? 0 : 4 }}>{msg.time}</span>
      </div>
    </div>
  );
}

/* ── Typing indicator (three animated dots) ───────────────────────────── */
function TypingIndicator() {
  return (
    <div style={{ display: 'flex', gap: 10 }}>
      <BotAvatar size={28} />
      <div style={{ padding: '12px 16px', borderRadius: 16, borderTopLeftRadius: 4, background: '#1a2535', border: '1px solid rgba(255,255,255,0.05)', display: 'flex', alignItems: 'center', gap: 5 }}>
        {[0, 0.2, 0.4].map((delay, i) => (
          <span key={i} style={{ display: 'inline-block', width: 6, height: 6, borderRadius: '50%', background: '#52525b', animation: `nort-typing-dot 1.2s ease-in-out ${delay}s infinite` }} />
        ))}
      </div>
    </div>
  );
}

/* ── Main NortBot section export ──────────────────────────────────────── */
export default function NortBot() {
  const [messages, setMessages]   = useState(SEED_MESSAGES);
  const [typing,   setTyping]     = useState(false);
  const [input,    setInput]      = useState('');
  const [responseIdx, setIdx]     = useState(0);
  const scrollRef                 = useRef(null);

  /* Auto-scroll chat to bottom whenever messages change */
  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, typing]);

  /* Pick the correct canned response based on keywords in the query */
  function pickResponse(text) {
    const t = text.toLowerCase();
    if (t.includes('hot') || t.includes('today') || t.includes('best')) return RESPONSES.hot;
    if (t.includes('eth') || t.includes('5k'))                          return RESPONSES.eth;
    if (t.includes('rocket') || t.includes('nba'))                      return RESPONSES.rockets;
    if (t.includes('top') || t.includes('pick'))                        return RESPONSES.picks;
    const reply = RESPONSES.default[responseIdx % RESPONSES.default.length];
    setIdx(i => i + 1);
    return reply;
  }

  /* Send a message: user bubble → typing → bot reply */
  function sendMessage(preset) {
    const text = (preset ?? input).trim();
    if (!text) return;
    setInput('');

    const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    /* Append user message */
    setMessages(prev => [...prev, { from: 'user', html: text, time }]);
    setTyping(true);

    /* Simulate bot thinking delay (1.1–1.5 s) */
    setTimeout(() => {
      const reply = pickResponse(text);
      setTyping(false);
      setMessages(prev => [...prev, { from: 'bot', html: reply, time }]);
    }, 1100 + Math.random() * 400);
  }

  return (
    /* ── Section wrapper ───────────────────────────── */
    <section id="nort-bot" style={{ padding: '96px 0', background: '#000', position: 'relative', overflow: 'visible' }}>

      {/* Custom gradient background image */}
      <div style={{
        position: 'absolute', inset: 0, zIndex: 0,
        backgroundImage: "url('/images/bg-nortbot.png')",
        backgroundSize: 'cover',
        backgroundPosition: 'center',
        backgroundRepeat: 'no-repeat',
        opacity: 0.85,
      }} />

      {/* Dot grid on top */}
      <div style={{
        position: 'absolute', inset: 0, zIndex: 1, pointerEvents: 'none',
        backgroundImage: 'radial-gradient(rgba(255,255,255,0.12) 1px, transparent 1px)',
        backgroundSize: '28px 28px',
        maskImage: 'radial-gradient(ellipse 90% 90% at 50% 50%, black 30%, transparent 100%)',
        WebkitMaskImage: 'radial-gradient(ellipse 90% 90% at 50% 50%, black 30%, transparent 100%)',
      }} />

      

      <div style={{ maxWidth: 1152, margin: '0 auto', padding: '0 24px', position: 'relative', zIndex: 2 }}>

        {/* ── Section header ───────────────────────── */}
        <div className="fade-up" style={{ textAlign: 'center', maxWidth: 600, margin: '0 auto 56px' }}>
          <h2 style={{ fontFamily: 'var(--font-display)', fontSize: 'clamp(28px,4vw,42px)', fontWeight: 800, letterSpacing: '-0.03em', color: '#f4f4f5', marginBottom: 16 }}>
            Chat with your NORT Bot
          </h2>
          <p style={{ fontSize: 15, color: '#71717a', lineHeight: 1.65 }}>
            Ask anything about Polymarket signals, get real-time analysis, and let NORT Bot guide your next trade — all in plain English.
          </p>
          <p style={{ fontSize: 13, color: '#52525b', marginTop: 10, lineHeight: 1.6 }}>
            Enjoy Premium AI features with flexible payments. It's pay per use — no subscriptions, no commitments.
          </p>
        </div>

        {/* ── Two-panel grid ───────────────────────── */}
        <div className="fade-up nort-bot-grid">

          {/* ── LEFT: Spline 3D robot model ──────────── */}
          {/* Outer wrapper handles the float animation — no overflow:hidden here
              so the upward movement isn't clipped at the top edge */}
          <div style={{ animation: 'nort-bot-float 5s ease-in-out infinite' }}>
          <div id="nort-spline-panel" style={{ position: 'relative', borderRadius: 20, overflow: 'hidden', border: '1px solid rgba(255,255,255,0.06)', background: '#0a1628', height: '100%' }}>

            {/* Spline iframe — loads the 3D N-Core V2 robot */}
            <div style={{ position: 'relative', width: '100%', height: '100%', overflow: 'hidden', borderRadius: 'inherit' }}>
              <iframe
                src="https://my.spline.design/r4xbotcopy-2h2YnhCwt7gJzzeufGABes7t/"
                frameBorder="0"
                width="100%"
                height="100%"
                loading="lazy"
                allow="autoplay"
                style={{ position: 'absolute', top: -2, left: -2, width: 'calc(100% + 4px)', height: 'calc(100% + 60px)', border: 'none', pointerEvents: 'auto' }}
              />
              {/* Mask: hides Spline branding at the bottom */}
              <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: 54, background: '#0a1628', zIndex: 10, pointerEvents: 'none', borderRadius: '0 0 1.25rem 1.25rem' }} />
              {/* Mask: hides top-right Spline UI controls */}
              <div style={{ position: 'absolute', top: 0, right: 0, width: 140, height: 46, background: '#0a1628', zIndex: 10, pointerEvents: 'none', borderRadius: '0 1.25rem 0 0' }} />
            </div>

            {/* Live badge bottom-left */}
            <div style={{ position: 'absolute', bottom: 18, left: 18, zIndex: 20 }}>
              <div style={{ display: 'inline-flex', alignItems: 'center', gap: 8, padding: '6px 14px', borderRadius: 999, border: '1px solid rgba(0,229,176,0.25)', background: 'rgba(0,0,0,0.5)', backdropFilter: 'blur(12px)' }}>
                <div style={{ position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#00e5b0', boxShadow: '0 0 8px #00e5b0' }} />
                </div>
                <span style={{ fontSize: 10, fontFamily: 'Space Grotesk, monospace', color: '#00e5b0', letterSpacing: '0.12em', textTransform: 'uppercase' }}>NORT Bot · N-Core V2</span>
              </div>
            </div>
          </div>{/* end nort-spline-panel */}
          </div>{/* end float wrapper */}

          {/* ── RIGHT: Chat panel ─────────────────────── */}
          <div id="nort-chat-panel" style={{ display: 'flex', flexDirection: 'column', borderRadius: 20, border: '1px solid rgba(255,255,255,0.06)', overflow: 'hidden', background: '#0d1117' }}>

            {/* Chat header: avatar, name, live pill */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '16px 20px', borderBottom: '1px solid rgba(255,255,255,0.05)', background: '#111820', flexShrink: 0 }}>
              <div style={{ position: 'relative' }}>
                <BotAvatar size={38} />
                {/* Online indicator dot */}
                <div style={{ position: 'absolute', bottom: -1, right: -1, width: 12, height: 12, borderRadius: '50%', background: '#00e5b0', border: '2px solid #111820', boxShadow: '0 0 6px #00e5b0' }} />
              </div>
              <div>
                <p style={{ margin: 0, fontSize: 13, fontWeight: 600, color: '#f4f4f5', fontFamily: 'Space Grotesk, sans-serif', letterSpacing: '-0.01em' }}>Nort Agent</p>
                <p style={{ margin: 0, fontSize: 10, color: '#52525b', fontFamily: 'Space Grotesk, monospace', marginTop: 1 }}>Model: N-Core V2 · Online</p>
              </div>
              {/* Live badge top-right */}
              <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 6, padding: '4px 12px', borderRadius: 999, border: '1px solid rgba(0,229,176,0.25)', background: 'rgba(0,229,176,0.08)' }}>
                <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#00e5b0', animation: 'nort-typing-dot 1.6s ease-in-out infinite' }} />
                <span style={{ fontSize: 9, fontFamily: 'Space Grotesk, monospace', color: '#00e5b0', letterSpacing: '0.12em', textTransform: 'uppercase' }}>Live</span>
              </div>
            </div>

            {/* Scrollable messages area */}
            <div ref={scrollRef} style={{ flex: 1, overflowY: 'auto', padding: 20, display: 'flex', flexDirection: 'column', gap: 16, scrollbarWidth: 'thin', scrollbarColor: '#27272a transparent' }}>
              {messages.map((msg, i) => <ChatBubble key={i} msg={msg} />)}
              {typing && <TypingIndicator />}
            </div>

            {/* Quick-chip buttons */}
            <div style={{ padding: '0 20px 10px', display: 'flex', gap: 8, flexWrap: 'wrap', flexShrink: 0 }}>
              {CHIPS.map(chip => (
                <button key={chip.label} onClick={() => sendMessage(chip.query)} className="nort-chip">
                  {chip.label}
                </button>
              ))}
            </div>

            {/* Text input + send button */}
            <div style={{ padding: '0 20px 20px', flexShrink: 0 }}>
              <div className="nort-input-wrap">
                <input
                  type="text"
                  className="nort-input"
                  placeholder="Command Nort..."
                  value={input}
                  onChange={e => setInput(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter') sendMessage(); }}
                />
                <button className="nort-send-btn" onClick={() => sendMessage()}>
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <path d="m22 2-7 20-4-9-9-4z"/><path d="M22 2 11 13"/>
                  </svg>
                </button>
              </div>
            </div>

          </div>{/* end chat panel */}
        </div>{/* end two-panel grid */}
      </div>{/* end container */}
    </section>
  );
}
