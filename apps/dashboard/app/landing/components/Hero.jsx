'use client';
import { useEffect, useState } from 'react';
import { usePrivy } from '@privy-io/react-auth';
import LiquidEther from './LiquidEther';

const TICKER_ITEMS = [
  { label:'BTC >$120K',           side:'YES', pct:'67%', heat:'HOT 🔥' },
  { label:'Rockets 52.5 wins',    side:'YES', pct:'54%', heat:'WARM'   },
  { label:'ETH flippening',       side:'NO',  pct:'78%', heat:'COOL'   },
  { label:'Fed rate cut Q3',      side:'YES', pct:'61%', heat:'WARM'   },
  { label:'Trump tariffs lifted', side:'NO',  pct:'55%', heat:'HOT 🔥' },
  { label:'Nvidia >$200',         side:'YES', pct:'72%', heat:'HOT 🔥' },
];

export default function Hero() {
  const { login, ready } = usePrivy();
  const [reducedMotion, setReducedMotion] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    setReducedMotion(mq.matches);
    const h = (e) => setReducedMotion(e.matches);
    mq.addEventListener('change', h);
    return () => mq.removeEventListener('change', h);
  }, []);

  return (
    <section style={{ position:'relative', minHeight:'100vh', display:'flex', flexDirection:'column',
      alignItems:'center', justifyContent:'center', paddingTop:96, paddingBottom:80, overflow:'hidden' }}>

      {/* Layer 1 — animated background */}
      <div style={{ position:'absolute', inset:0, zIndex:1 }}>
        {reducedMotion ? (
          <div style={{ width:'100%', height:'100%',
            background:'radial-gradient(ellipse 70% 60% at 20% 30%, rgba(0,200,150,0.18) 0%, transparent 60%), radial-gradient(ellipse 60% 50% at 80% 70%, rgba(26,127,232,0.18) 0%, transparent 60%)' }} />
        ) : (
          <LiquidEther colors={['#1A7FE8','#1A7FE8','#37f1ce']} mouseForce={25} cursorSize={120}
            isViscous={false} viscous={40} iterationsViscous={24} iterationsPoisson={16}
            resolution={0.35} isBounce={false} autoDemo autoSpeed={0.4} autoIntensity={2.5}
            takeoverDuration={0.25} autoResumeDelay={0} autoRampDuration={0.3} />
        )}
      </div>

      {/* Layer 2 — dot grid */}
      <div style={{ position:'absolute', inset:0, zIndex:2, pointerEvents:'none',
        backgroundImage:'radial-gradient(rgba(255,255,255,0.12) 1px, transparent 1px)',
        backgroundSize:'28px 28px',
        maskImage:'radial-gradient(ellipse 85% 85% at 50% 50%, black 30%, transparent 100%)',
        WebkitMaskImage:'radial-gradient(ellipse 85% 85% at 50% 50%, black 30%, transparent 100%)' }} />

      {/* Layer 3 — glassmorphism card */}
      <div className="l-fade-up" style={{ position:'relative', zIndex:10, width:'100%', maxWidth:1152, margin:'0 auto', padding:'0 24px' }}>
        <div style={{ background:'rgba(5,8,18,0.30)', backdropFilter:'blur(20px)', WebkitBackdropFilter:'blur(20px)',
          border:'1px solid rgba(255,255,255,0.13)', borderRadius:28, padding:'clamp(32px,5vw,60px)',
          boxShadow:'0 0 0 1px rgba(0,200,150,0.12), 0 32px 80px rgba(0,0,0,0.35), inset 0 1px 0 rgba(255,255,255,0.10)',
          textAlign:'center' }}>

          <div style={{ marginBottom:14 }}>
            <span style={{ display:'inline-flex', alignItems:'center', gap:8, fontSize:13,
              fontFamily:'var(--font-body)', color:'var(--text-3)', letterSpacing:'0.06em' }}>Welcome to</span>
          </div>

          <h1 style={{ fontFamily:'var(--font-display)', fontWeight:800, fontSize:'clamp(64px,12vw,120px)',
            lineHeight:0.9, letterSpacing:'-0.04em', color:'var(--text)', marginBottom:16 }}>NORT</h1>
          <p style={{ fontFamily:'var(--font-display)', fontWeight:700, fontSize:'clamp(13px,1.5vw,16px)',
            color:'var(--accent)', letterSpacing:'0.12em', textTransform:'uppercase', marginBottom:24 }}>
            Polymarket Trading Made Easy
          </p>
          <p style={{ fontFamily:'var(--font-body)', fontSize:'clamp(15px,2vw,18px)', color:'var(--text-2)',
            lineHeight:1.65, maxWidth:520, margin:'0 auto 36px' }}>
            NORT ranks the best Polymarket opportunities in real time — then lets you ask AI for a plain-English breakdown before you trade.
          </p>

          <div style={{ display:'flex', gap:12, justifyContent:'center', flexWrap:'wrap', marginBottom:40 }}>
            <button
              className="l-btn l-btn-primary"
              style={{ border:'none', cursor:'pointer' }}
              onClick={login}
              disabled={!ready}
            >
              Start Trading Free
              <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 12h14m0 0l-7-7m7 7l-7 7"/>
              </svg>
            </button>
            <a href="#l-features" className="l-btn l-btn-ghost">See How It Works</a>
          </div>

          <div style={{ display:'flex', alignItems:'center', justifyContent:'center', gap:'clamp(20px,4vw,48px)' }}>
            {[['2.4K+','Beta Signups'],['31','Live Signals'],['Free','To Start']].map(([v,l],i) => (
              <div key={l} style={{ display:'flex', alignItems:'center', gap:'clamp(20px,4vw,48px)' }}>
                {i > 0 && <div style={{ width:1, height:32, background:'var(--border)' }} />}
                <div style={{ textAlign:'center' }}>
                  <div style={{ fontFamily:'var(--font-display)', fontWeight:800, fontSize:22, color:'var(--text)', letterSpacing:'-0.02em' }}>{v}</div>
                  <div style={{ fontSize:10, color:'var(--text-3)', letterSpacing:'0.08em', textTransform:'uppercase', fontFamily:'var(--font-display)', marginTop:3 }}>{l}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Ticker */}
      <div role="marquee" aria-label="Live market signals" style={{ position:'absolute', bottom:0, left:0, right:0, zIndex:10,
        borderTop:'1px solid var(--border)', background:'rgba(5,8,18,0.88)', backdropFilter:'blur(12px)', padding:'9px 0', overflow:'hidden' }}>
        <div className="l-ticker-track" style={{ display:'flex', gap:48, width:'max-content' }}>
          {[...TICKER_ITEMS, ...TICKER_ITEMS].map((item,i) => (
            <div key={i} aria-hidden={i >= TICKER_ITEMS.length} style={{ display:'flex', alignItems:'center', gap:8, whiteSpace:'nowrap' }}>
              <span style={{ width:5, height:5, borderRadius:'50%', background:'var(--accent)', flexShrink:0, display:'inline-block' }}/>
              <span style={{ fontSize:11, fontFamily:'var(--font-display)', color:'var(--text-2)', fontWeight:500 }}>{item.label}</span>
              <span style={{ fontSize:11, fontFamily:'var(--font-display)', color:'var(--accent)', fontWeight:700 }}>{item.side} {item.pct}</span>
              <span style={{ fontSize:10, color:'var(--text-3)', fontFamily:'var(--font-display)' }}>{item.heat}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
