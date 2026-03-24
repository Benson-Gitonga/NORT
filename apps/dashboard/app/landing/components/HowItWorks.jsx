/**
 * HowItWorks.js
 * ─────────────────────────────────────────────
 * Pipeline-style "How It Works" section.
 *
 * LAYOUT:
 *   - Vertical spine runs down the centre on desktop.
 *   - Each step alternates: copy LEFT / card RIGHT, then card LEFT / copy RIGHT.
 *   - A glowing beam animates down the spine continuously.
 *   - Node dots sit on the spine at each step intersection.
 *   - Steps fade + slide in via IntersectionObserver as you scroll.
 *
 * COLOURS: All use NORT CSS vars (--accent, --bg-1, --border etc.)
 *   Beam colour:  --accent  (#00C896 teal)
 *   Node colours: teal for first/last, blue for middle steps.
 *
 * TO EDIT STEPS: Update the STEPS array below — title, desc, side, card.
 * TO CHANGE BEAM COLOUR: Edit the gradient in .hw-beam (globals addition).
 * TO CHANGE ANIMATION SPEED: Edit the 3.5s in .hw-beam animation.
 * ─────────────────────────────────────────────
 */
'use client';
import { useEffect, useRef } from 'react';

/* ── Step card components ─────────────────────────────────────── */

/* Step 1: Live signal trending card */
function CardFindMarkets() {
  return (
    <div style={{ background:'rgba(13,20,40,0.85)', backdropFilter:'blur(12px)', border:'1px solid var(--border)', borderRadius:14, padding:20, minHeight:110, display:'flex', flexDirection:'column', justifyContent:'space-between' }}>
      <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:10 }}>
        <span style={{ fontSize:10, fontWeight:700, letterSpacing:'0.12em', color:'var(--text-3)', textTransform:'uppercase', fontFamily:'var(--font-display)' }}>Live Signal</span>
        <div style={{ display:'flex', alignItems:'center', gap:5, padding:'3px 8px', borderRadius:6, background:'rgba(0,200,150,0.1)', border:'1px solid rgba(0,200,150,0.2)' }}>
          <span style={{ width:6, height:6, borderRadius:'50%', background:'var(--accent)', display:'inline-block', animation:'blink 1.4s ease-in-out infinite' }}></span>
          <span style={{ fontSize:9, fontWeight:800, color:'var(--accent)', letterSpacing:'0.08em', textTransform:'uppercase', fontFamily:'var(--font-display)' }}>Trending ↑</span>
        </div>
      </div>
      <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between' }}>
        <div>
          <span style={{ fontSize:13, fontWeight:600, color:'var(--text)', display:'block', fontFamily:'var(--font-display)' }}>Will BTC hit $100k?</span>
          <div style={{ display:'flex', alignItems:'center', gap:8, marginTop:5 }}>
            <span style={{ fontSize:9, color:'var(--text-3)', fontFamily:'var(--font-display)', letterSpacing:'0.06em' }}>VOL: 8.4×</span>
            <div style={{ height:3, width:52, background:'var(--border)', borderRadius:99, overflow:'hidden' }}>
              <div style={{ height:'100%', width:'85%', background:'var(--accent)', borderRadius:99, boxShadow:'0 0 8px var(--accent)' }}></div>
            </div>
          </div>
        </div>
        <span style={{ fontSize:14, fontFamily:'var(--font-display)', fontWeight:700, color:'var(--accent)' }}>+18.4%</span>
      </div>
    </div>
  );
}

/* Step 2: AI analysis chat card */
function CardAnalyze() {
  return (
    <div style={{ background:'rgba(13,20,40,0.85)', backdropFilter:'blur(12px)', border:'1px solid var(--border)', borderRadius:14, padding:16, minHeight:110 }}>
      <div style={{ display:'flex', flexDirection:'column', gap:8 }}>
        <div style={{ alignSelf:'flex-end', background:'rgba(26,127,232,0.15)', border:'1px solid rgba(26,127,232,0.25)', borderRadius:10, padding:'6px 12px', maxWidth:'80%' }}>
          <p style={{ fontSize:10, color:'#93c5fd', fontFamily:'var(--font-body)', margin:0 }}>Should I buy YES?</p>
        </div>
        <div style={{ alignSelf:'flex-start', background:'rgba(255,255,255,0.04)', border:'1px solid var(--border)', borderRadius:10, padding:'8px 12px', maxWidth:'90%' }}>
          <div style={{ display:'flex', alignItems:'center', gap:5, marginBottom:4 }}>
            <span style={{ width:6, height:6, borderRadius:'50%', background:'var(--accent)', display:'inline-block' }}></span>
            <span style={{ fontSize:9, fontWeight:700, color:'var(--accent)', letterSpacing:'0.1em', textTransform:'uppercase', fontFamily:'var(--font-display)' }}>NORT Bot</span>
          </div>
          <p style={{ fontSize:10, color:'var(--text-2)', lineHeight:1.5, margin:0, fontFamily:'var(--font-body)' }}>Bullish sentiment. Key drivers: ETF inflows and whale accumulation.</p>
        </div>
      </div>
    </div>
  );
}

/* Step 3: Signal recommendation card */
function CardSignal() {
  return (
    <div style={{ background:'rgba(13,20,40,0.85)', backdropFilter:'blur(12px)', border:'1px solid var(--border)', borderRadius:14, padding:20, minHeight:110, display:'flex', alignItems:'center', justifyContent:'space-between' }}>
      <div>
        <span style={{ fontSize:10, fontFamily:'var(--font-display)', color:'var(--text-3)', textTransform:'uppercase', letterSpacing:'0.1em', display:'block', marginBottom:6 }}>Recommendation</span>
        <div style={{ padding:'6px 16px', borderRadius:8, background:'rgba(0,200,150,0.15)', border:'1px solid rgba(0,200,150,0.35)' }}>
          <span style={{ fontSize:18, fontWeight:800, color:'var(--accent)', fontFamily:'var(--font-display)' }}>BUY YES</span>
        </div>
      </div>
      <div style={{ textAlign:'right' }}>
        <span style={{ fontSize:10, fontFamily:'var(--font-display)', color:'var(--text-3)', textTransform:'uppercase', letterSpacing:'0.1em', display:'block', marginBottom:4 }}>Confidence</span>
        <span style={{ fontSize:26, fontWeight:800, color:'var(--text)', fontFamily:'var(--font-display)' }}>78%</span>
      </div>
    </div>
  );
}

/* Step 4: Place trade card */
function CardTrade() {
  return (
    <div style={{ background:'rgba(13,20,40,0.85)', backdropFilter:'blur(12px)', border:'1px solid var(--border)', borderRadius:14, padding:16, minHeight:110, display:'flex', flexDirection:'column', justifyContent:'center' }}>
      <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:12 }}>
        <div style={{ display:'flex', background:'var(--bg-2)', borderRadius:8, padding:2, border:'1px solid var(--border)' }}>
          <span style={{ padding:'4px 14px', borderRadius:6, background:'var(--accent)', fontSize:10, fontWeight:800, color:'#000', fontFamily:'var(--font-display)' }}>YES</span>
          <span style={{ padding:'4px 14px', fontSize:10, fontWeight:700, color:'var(--text-3)', fontFamily:'var(--font-display)' }}>NO</span>
        </div>
        <span style={{ fontSize:12, fontFamily:'var(--font-display)', color:'var(--text)', fontWeight:600 }}>$500.00</span>
      </div>
      <div style={{ width:'100%', padding:'8px 0', background:'linear-gradient(135deg,var(--accent),var(--blue))', borderRadius:8, textAlign:'center', fontSize:11, fontWeight:800, color:'#fff', letterSpacing:'0.08em', fontFamily:'var(--font-display)', cursor:'pointer' }}>
        CONFIRM TRADE
      </div>
    </div>
  );
}

/* Step 5: Track results card */
function CardTrack() {
  return (
    <div style={{ background:'rgba(13,20,40,0.85)', backdropFilter:'blur(12px)', border:'1px solid var(--border)', borderRadius:14, padding:20, minHeight:110, display:'flex', flexDirection:'column', justifyContent:'space-between' }}>
      <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between' }}>
        <div style={{ display:'flex', alignItems:'center', gap:7 }}>
          <span style={{ width:8, height:8, borderRadius:'50%', background:'var(--accent)', display:'inline-block', animation:'blink 2s ease-in-out infinite' }}></span>
          <span style={{ fontSize:10, fontWeight:700, color:'var(--text)', letterSpacing:'0.1em', textTransform:'uppercase', fontFamily:'var(--font-display)' }}>Active Trade</span>
        </div>
        <span style={{ fontSize:11, fontFamily:'var(--font-display)', fontWeight:700, color:'var(--accent)' }}>+$142.50</span>
      </div>
      <div style={{ display:'flex', alignItems:'flex-end', gap:3, height:36 }}>
        {[40,60,50,80,100].map((h,i) => (
          <div key={i} style={{ flex:1, height:`${h}%`, borderRadius:'3px 3px 0 0', background: i >= 3 ? `rgba(0,200,150,${i===4?1:0.5})` : 'var(--border)', boxShadow: i===4 ? '0 0 10px var(--accent)' : 'none' }}></div>
        ))}
      </div>
      <div style={{ display:'flex', justifyContent:'space-between', fontSize:9, fontFamily:'var(--font-display)', color:'var(--text-3)', letterSpacing:'0.06em', textTransform:'uppercase' }}>
        <span>BTC/USD Market</span>
        <span>Live</span>
      </div>
    </div>
  );
}

/* ── STEPS DATA ────────────────────────────────────────────────
   side: 'left' = copy left / card right
         'right' = card left / copy right
   nodeColor: colour of the dot on the spine
─────────────────────────────────────────────────────────────── */
const STEPS = [
  { num:'01', title:'Browse Signals',   desc:'The signals engine scans active crypto and sports markets on Polymarket and ranks them by price momentum and volume spikes — surfacing what\'s actually moving right now.',          side:'left',  nodeColor:'var(--accent)', Card: CardFindMarkets },
  { num:'02', title:'Ask AI for Advice',desc:'Tap any signal to ask OpenClaw for a plain-English breakdown — key drivers, risks, and a suggested position. AI advice is on-demand, not automatic.',                              side:'right', nodeColor:'var(--accent)', Card: CardAnalyze    },
  { num:'03', title:'Get a Signal',     desc:'See a clear recommendation — BUY YES, BUY NO, or WAIT — along with a confidence score from the signals engine based on momentum and volume data.',                               side:'left',  nodeColor:'var(--accent)', Card: CardSignal     },
  { num:'04', title:'Place a Trade',    desc:'Place paper trades directly from the dashboard or Telegram bot. No external tools, no complex setup — just pick a market, choose a side, and stake.',                            side:'right', nodeColor:'var(--accent)', Card: CardTrade      },
  { num:'05', title:'Track Results',    desc:'Follow your open positions in real time. Monitor P&L, win rate, and XP progress on your dashboard — and see how you stack up on the leaderboard.',                              side:'left',  nodeColor:'var(--accent)', Card: CardTrack      },
];

export default function HowItWorks() {
  const sectionRef = useRef(null);

  /* IntersectionObserver — adds .hw-visible to each .hw-step and .hw-header
     as they scroll into view, triggering CSS transitions */
  useEffect(() => {
    const section = sectionRef.current;
    if (!section) return;
    const targets = section.querySelectorAll('.hw-step, .hw-header');
    const observer = new IntersectionObserver(
      entries => entries.forEach(e => { if (e.isIntersecting) { e.target.classList.add('hw-visible'); observer.unobserve(e.target); } }),
      { threshold: 0.2, rootMargin: '0px 0px -8% 0px' }
    );
    targets.forEach(el => observer.observe(el));
    return () => observer.disconnect();
  }, []);

  return (
    <section id="l-how-it-works" ref={sectionRef} style={{ padding:'96px 0', background:'#000', position:'relative', overflow:'hidden' }}>

      {/* Custom gradient background image */}
      <div style={{
        position:'absolute', inset:0, zIndex:0,
        backgroundImage:"url('/images/bg-howitworks.png')",
        backgroundSize:'cover',
        backgroundPosition:'center',
        backgroundRepeat:'no-repeat',
        opacity:0.85,
      }} />

      {/* Dot grid on top */}
      <div style={{
        position:'absolute', inset:0, zIndex:1, pointerEvents:'none',
        backgroundImage:'radial-gradient(rgba(255,255,255,0.12) 1px, transparent 1px)',
        backgroundSize:'28px 28px',
        maskImage:'radial-gradient(ellipse 90% 90% at 50% 50%, black 30%, transparent 100%)',
        WebkitMaskImage:'radial-gradient(ellipse 90% 90% at 50% 50%, black 30%, transparent 100%)',
      }} />

      {/* Inset shadows top + bottom */}
      <div style={{ position:'absolute', inset:0, zIndex:2, pointerEvents:'none', boxShadow:'inset 0 20px 40px rgba(0,0,0,0.4), inset 0 -20px 40px rgba(0,0,0,0.4)' }}></div>

      <div style={{ maxWidth:1152, margin:'0 auto', padding:'0 24px', position:'relative', zIndex:3 }}>

        {/* ── Section header ───────────────────────── */}
        <div className="hw-header" style={{ textAlign:'center', maxWidth:600, margin:'0 auto 72px', opacity:0, transform:'translateY(24px)', transition:'opacity 0.8s ease, transform 0.8s ease' }}>
          <span className="pill" style={{ marginBottom:16, display:'inline-flex' }}>How It Works</span>
          <h2 style={{ fontFamily:'var(--font-display)', fontSize:'clamp(28px,4vw,44px)', fontWeight:800, letterSpacing:'-0.03em', color:'var(--text)', marginBottom:16 }}>
            How NORT works
          </h2>
          <p style={{ fontSize:16, color:'var(--text-2)', lineHeight:1.65, fontFamily:'var(--font-body)' }}>
            A signals engine ranks the best Polymarket opportunities in real time. Ask AI for advice on any of them. Then trade — right from the app or Telegram.
          </p>
        </div>

        {/* ── Pipeline shell ───────────────────────── */}
        <div style={{ position:'relative', maxWidth:900, margin:'0 auto' }}>

          {/* Vertical spine tube — no border, just the inner track */}
          <div style={{ position:'absolute', left:'50%', top:0, bottom:0, width:18, transform:'translateX(-50%)', borderRadius:999, zIndex:0 }}>

            {/* Inner track + animated beam */}
            <div style={{ position:'absolute', left:'50%', top:16, bottom:16, width:2, transform:'translateX(-50%)', borderRadius:999, background:'rgba(63,63,70,0.95)', overflow:'hidden' }}>
              <div style={{ position:'absolute', left:'50%', top:0, width:2, height:120, transform:'translateX(-50%)', background:'linear-gradient(to bottom, transparent, var(--accent), transparent)', boxShadow:'0 0 16px var(--accent-glow)', animation:'hw-beam 3.5s linear infinite' }}></div>
            </div>
          </div>

          {/* ── Steps ───────────────────────────────── */}
          {STEPS.map((step, i) => {
            const isLeft = step.side === 'left'; /* copy left = card right */
            return (
              <div key={step.num} className="hw-step" style={{ position:'relative', zIndex:10, display:'grid', gridTemplateColumns:'1fr 1fr', alignItems:'center', gap:'2.25rem', minHeight:120, marginBottom: i < STEPS.length - 1 ? '4rem' : 0, opacity:0, transform:'translateY(32px)', transition:'opacity 0.8s ease, transform 0.8s ease' }}>

                {/* Left column */}
                <div className="hw-step-copy" style={{ opacity:0, transform:'translateY(16px)', transition:'opacity 0.7s ease 0.05s, transform 0.7s ease 0.05s', ...(isLeft ? { textAlign:'right', paddingRight:'3.5rem' } : { paddingLeft:'3.5rem' }) }}>
                  {isLeft ? (
                    <>
                      <h3 style={{ fontFamily:'var(--font-display)', fontSize:'clamp(22px,2.5vw,28px)', fontWeight:700, color:'var(--text)', letterSpacing:'-0.03em', lineHeight:1.15 }}>{step.title}</h3>
                      <p style={{ marginTop:10, fontSize:15, lineHeight:1.6, color:'var(--text-2)', fontFamily:'var(--font-body)', marginLeft:'auto', maxWidth:'26rem' }}>{step.desc}</p>
                    </>
                  ) : (
                    <step.Card />
                  )}
                </div>

                {/* Right column */}
                <div className="hw-step-card" style={{ opacity:0, transform:'translateY(16px)', transition:'opacity 0.7s ease 0.3s, transform 0.7s ease 0.3s', ...(isLeft ? { paddingLeft:'3.5rem' } : { paddingRight:'3.5rem' }) }}>
                  {isLeft ? (
                    <step.Card />
                  ) : (
                    <>
                      <h3 style={{ fontFamily:'var(--font-display)', fontSize:'clamp(22px,2.5vw,28px)', fontWeight:700, color:'var(--text)', letterSpacing:'-0.03em', lineHeight:1.15 }}>{step.title}</h3>
                      <p style={{ marginTop:10, fontSize:15, lineHeight:1.6, color:'var(--text-2)', fontFamily:'var(--font-body)', maxWidth:'26rem' }}>{step.desc}</p>
                    </>
                  )}
                </div>

                {/* Spine node — sits on the centre line */}
                <div className="hw-step-node" style={{ position:'absolute', left:'50%', top:'50%', width:36, height:36, transform:'translate(-50%,-50%)', display:'flex', alignItems:'center', justifyContent:'center', zIndex:20, opacity:0, transition:'opacity 0.7s ease 0.18s' }}>
                  <div style={{ position:'relative', width:'100%', height:'100%', borderRadius:'50%', border:`1px solid rgba(63,63,70,0.8)`, background:`radial-gradient(circle, var(--bg-2), var(--bg))`, display:'flex', alignItems:'center', justifyContent:'center', boxShadow:'0 6px 20px rgba(0,0,0,0.4)' }}>
                    {/* Static ring — no pulse */}
                    <div style={{ position:'absolute', inset:-8, borderRadius:'50%', border:`1px solid ${step.nodeColor}`, opacity:0.25 }}></div>
                    {/* Coloured dot */}
                    <div style={{ width:10, height:10, borderRadius:'50%', background:step.nodeColor, boxShadow:`0 0 12px ${step.nodeColor}` }}></div>
                  </div>
                </div>

              </div>
            );
          })}

        </div>{/* end pipeline shell */}
      </div>{/* end container */}
    </section>
  );
}
