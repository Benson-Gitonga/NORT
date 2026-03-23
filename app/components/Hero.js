'use client';
/**
 * ═══════════════════════════════════════════════════════════════
 * Hero.js — Full-screen landing hero section
 * ═══════════════════════════════════════════════════════════════
 *
 * VISUAL LAYER STACK (bottom → top, z-index order):
 * ┌─────────────────────────────────────────────────────────┐
 * │ 0  section background  — static CSS mesh gradient       │
 * │    5 radial-gradient blobs baked directly into the CSS  │
 * │    background property. Zero JS, renders instantly.     │
 * ├─────────────────────────────────────────────────────────┤
 * │ 1  <LiquidEther>       — real WebGL fluid simulation    │
 * │    Three.js Navier-Stokes sim. Mouse/auto-driven.       │
 * │    transparent background lets CSS mesh show through.  │
 * ├─────────────────────────────────────────────────────────┤
 * │ 2  Dot-grid overlay    — 1px radial-gradient dots       │
 * │    Adds subtle texture. Vignette mask fades edges.      │
 * ├─────────────────────────────────────────────────────────┤
 * │ 10 Glassmorphism card  — frosted dark panel             │
 * │    backdrop-filter:blur(20px) + low opacity background  │
 * │    lets gradient layers bleed through visibly.          │
 * │    Contains: eyebrow, headline, subtext, CTAs,          │
 * │    stats row, app preview dashboard                     │
 * ├─────────────────────────────────────────────────────────┤
 * │ 10 Ticker strip        — absolute bottom, blurred bg    │
 * │    Scrolling live signal feed, loops seamlessly.        │
 * └─────────────────────────────────────────────────────────┘
 *
 * FONTS USED:
 *   Syne 800       → NORT headline (--font-display)
 *   Plus Jakarta   → body copy, eyebrow (--font-body)
 *   Goldman        → badges, tags (--font-heading)
 *
 * TO ADJUST GRADIENT VISIBILITY:
 *   - Brighter  → raise rgba opacity values in section background
 *   - Dimmer    → lower rgba opacity values in section background
 *   - Glass opacity → change rgba(5,8,18, X) — lower X = more visible
 * ═══════════════════════════════════════════════════════════════
 */

import { useEffect, useState } from 'react';
import LiquidEther from './LiquidEther';

/* ─────────────────────────────────────────────────────────────
   DATA — Static arrays defined outside the component so they
   never re-create on render. Safe to edit without touching JSX.
   ───────────────────────────────────────────────────────────── */

/**
 * TICKER_ITEMS
 * Feeds the scrolling live-signals strip at the bottom of the hero.
 * Duplicated ([...arr, ...arr]) so the CSS scroll-x animation loops
 * seamlessly without a visible jump.
 */
const TICKER_ITEMS = [
  { label:'BTC >$120K',           side:'YES', pct:'67%', heat:'HOT 🔥' },
  { label:'Rockets 52.5 wins',    side:'YES', pct:'54%', heat:'WARM'   },
  { label:'ETH flippening',       side:'NO',  pct:'78%', heat:'COOL'   },
  { label:'Fed rate cut Q3',      side:'YES', pct:'61%', heat:'WARM'   },
  { label:'Trump tariffs lifted', side:'NO',  pct:'55%', heat:'HOT 🔥' },
  { label:'Nvidia >$200',         side:'YES', pct:'72%', heat:'HOT 🔥' },
];



/* ─────────────────────────────────────────────────────────────
   COMPONENT: LiquidEther (imported from ./LiquidEther.js)
   ─────────────────────────────────────────────────────────────
   Real WebGL Navier-Stokes fluid simulation.
   - colors: NORT teal (#00C896) + blue (#1A7FE8) + mid teal
   - autoDemo: runs automatically without user interaction
   - isViscous: thicker, more syrupy fluid movement
   - The canvas has alpha:true + transparent bgColor so the
     CSS mesh gradient underneath shows through it.
   - Mouse/touch interaction injects velocity into the fluid.
   To swap colours: change the colors array hex values.
   ───────────────────────────────────────────────────────────── */



/* ─────────────────────────────────────────────────────────────
   COMPONENT: Hero (default export)
   ─────────────────────────────────────────────────────────────
   Main hero section. Full-screen, centred, overflow:hidden
   to clip the LiquidEther blobs that extend beyond the viewport.
   ───────────────────────────────────────────────────────────── */
export default function Hero() {
  // Respect prefers-reduced-motion — swap animated WebGL blob for a
  // static CSS gradient so users with vestibular disorders aren't affected.
  const [reducedMotion, setReducedMotion] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    setReducedMotion(mq.matches);
    const handler = (e) => setReducedMotion(e.matches);
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, []);

  return (
    <section style={{
      position: 'relative', minHeight: '100vh',
      display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center',
      paddingTop: 96,   /* clears the fixed navbar height */
      paddingBottom: 80, /* space above the ticker strip */
      overflow: 'hidden',

      /*
       * LAYER 0 — Static CSS Mesh Gradient
       * ─────────────────────────────────────────────────────
       * 5 radial-gradient ellipses stacked as the section's
       * background. Renders INSTANTLY (no JS, no paint delay).
       *
       * Why two separate gradient systems (static + LiquidEther)?
       * The static mesh is always visible from frame 0. The
       * LiquidEther layer adds animated movement on top.
       * Together they give depth and life.
       *
       * Blob positions (at X% Y%):
       *   Top-left      10% 20%  → teal    0.45 opacity
       *   Top-right     90% 15%  → blue    0.42 opacity
       *   Bottom-right  80% 85%  → navy    0.35 opacity
       *   Bottom-left   15% 80%  → teal    0.32 opacity
       *   Centre        50% 50%  → blue    0.15 (subtle bloom)
       *
       * To adjust: raise/lower the last number in rgba(r,g,b,X)
       */
      
    }}>

      {/*
       * LAYER 1 — LiquidEther WebGL fluid simulation
       * Full-screen, absolute positioned, z-index 1.
       * colors: teal → mid-teal → blue matches NORT palette.
       * isViscous + viscous=40: thicker, slower-moving fluid.
       * autoDemo keeps it animated without user interaction.
       * mouseForce=25: strong response to cursor movement.
       */}
      {/* LAYER 1 — animated background.
          Full motion: LiquidEther WebGL fluid sim.
          Reduced motion: static teal→blue radial gradient — same palette,
          zero animation, respects vestibular/motion sensitivity. */}
      <div style={{ position:'absolute', inset:0, zIndex:1 }}>
        {reducedMotion ? (
          <div style={{
            width: '100%', height: '100%',
            background: 'radial-gradient(ellipse 70% 60% at 20% 30%, rgba(0,200,150,0.18) 0%, transparent 60%), radial-gradient(ellipse 60% 50% at 80% 70%, rgba(26,127,232,0.18) 0%, transparent 60%)',
          }} />
        ) : (
          <LiquidEther
            colors={['#1A7FE8','#1A7FE8','#37f1ce']}
            mouseForce={25}
            cursorSize={120}
            isViscous={false}
            viscous={40}
            iterationsViscous={24}
            iterationsPoisson={16}
            resolution={0.35}
            isBounce={false}
            autoDemo
            autoSpeed={0.4}
            autoIntensity={2.5}
            takeoverDuration={0.25}
            autoResumeDelay={0}
            autoRampDuration={0.3}
          />
        )}
      </div>

      {/*
       * LAYER 2 — Dot-grid texture overlay
       * A repeating 28×28px grid of 1px dots (radial-gradient trick).
       * Adds tactile depth without competing with the colour layers.
       *
       * maskImage: radial vignette — grid is visible in the centre,
       * fades to nothing at the edges so the gradient shines through
       * cleanly at the corners and sides.
       *
       * Dot opacity 0.045 — very subtle, only visible on close inspection.
       * Raise to 0.08–0.12 for a more prominent grid.
       */}
      <div style={{
        position: 'absolute', inset: 0, zIndex: 2, pointerEvents: 'none',
        backgroundImage: 'radial-gradient(rgba(255,255,255,0.12) 1px, transparent 1px)',
        backgroundSize: '28px 28px',
        maskImage: 'radial-gradient(ellipse 85% 85% at 50% 50%, black 30%, transparent 100%)',
        WebkitMaskImage: 'radial-gradient(ellipse 85% 85% at 50% 50%, black 30%, transparent 100%)',
      }} />

      {/*
       * LAYER 3 — Glassmorphism hero card
       * ─────────────────────────────────────────────────────
       * The frosted panel that contains all the hero content.
       *
       * GLASS EFFECT BREAKDOWN:
       *   background rgba(5,8,18, 0.30)  — dark but semi-transparent
       *                                    so gradient layers bleed
       *                                    through from behind
       *   backdropFilter blur(20px)      — frosts/blurs everything
       *                                    behind the card
       *   border rgba(255,255,255,0.13)  — subtle white edge highlight
       *   boxShadow ring rgba(0,200,150) — faint teal outer glow
       *   inset 0 1px rgba(white,0.10)  — top inner highlight
       *                                    simulates light hitting glass
       *
       * TUNING TIPS:
       *   More transparent → lower 0.30 toward 0.15
       *   More frosted     → raise blur(20px) toward blur(40px)
       *   More visible edge→ raise border opacity toward 0.25
       */}
      <div className="fade-up" style={{
        /* fade-up class: starts opacity:0 translateY(28px),
           ScrollAnimations.js adds .visible to trigger the transition */
        position: 'relative', zIndex: 10,
        width: '100%', maxWidth: 1152,
        margin: '0 auto', padding: '0 24px',
      }}>
        <div style={{
          background: 'rgba(5,8,18,0.30)',
          backdropFilter: 'blur(20px)',
          WebkitBackdropFilter: 'blur(20px)',
          border: '1px solid rgba(255,255,255,0.13)',
          borderRadius: 28,
          padding: 'clamp(32px, 5vw, 60px)', /* responsive padding */
          boxShadow: '0 0 0 1px rgba(0,200,150,0.12), 0 32px 80px rgba(0,0,0,0.35), inset 0 1px 0 rgba(255,255,255,0.10)',
          textAlign: 'center',
        }}>

          {/*
           * EYEBROW — "Welcome to"
           * Small label above the headline with a pulsing accent dot.
           * The dot uses the global `blink` keyframe (globals.css).
           */}
          <div style={{ marginBottom: 14 }}>
            <span style={{
              display: 'inline-flex', alignItems: 'center', gap: 8,
              fontSize: 13, fontFamily: 'var(--font-body)',
              color: 'var(--text-3)', letterSpacing: '0.06em',
            }}>
              Welcome to
            </span>
          </div>

          {/*
           * HEADLINE — "NORT"
           * clamp(64px, 12vw, 120px): fluid type scale —
           *   64px  minimum on very small screens
           *   12vw  scales with viewport width
           *   120px maximum on large screens
           * lineHeight 0.9 — tighter than default for display type
           */}
          {/* H1 includes keywords for SEO — visually "NORT" dominates,
              the subtitle line below it carries the keyword context
              for crawlers without disrupting the visual design. */}
          <h1 style={{
            fontFamily: 'var(--font-display)', fontWeight: 800,
            fontSize: 'clamp(64px, 12vw, 120px)',
            lineHeight: 0.9, letterSpacing: '-0.04em',
            color: 'var(--text)', marginBottom: 16,
          }}>NORT</h1>
          <p style={{
            fontFamily: 'var(--font-display)', fontWeight: 700,
            fontSize: 'clamp(13px, 1.5vw, 16px)',
            color: 'var(--accent)', letterSpacing: '0.12em',
            textTransform: 'uppercase', marginBottom: 24,
          }}>
            Polymarket Trading Made Easy
          </p>

          {/* SUBHEADING — value proposition */}
          <p style={{
            fontFamily: 'var(--font-body)', fontSize: 'clamp(15px,2vw,18px)',
            color: 'var(--text-2)', lineHeight: 1.65,
            maxWidth: 520, margin: '0 auto 36px',
          }}>
            NORT ranks the best Polymarket opportunities in real time — then lets you ask AI for a plain-English breakdown before you trade. Whether you're just starting out or already trading, NORT gives you the edge.
          </p>

          {/*
           * CTA BUTTONS
           * btn-primary — gradient teal→blue with glow shadow
           * btn-ghost   — dark navy with subtle border
           * Both defined in globals.css .btn / .btn-primary / .btn-ghost
           */}
          <div style={{ display:'flex', gap:12, justifyContent:'center', flexWrap:'wrap', marginBottom:40 }}>
            <a href="https://nort-rho.vercel.app" className="btn btn-primary">
              Start Trading Free
              <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 12h14m0 0l-7-7m7 7l-7 7"/>
              </svg>
            </a>
            <a href="#features" className="btn btn-ghost">See How It Works</a>
          </div>

          {/*
           * STATS ROW — 3 key metrics with divider lines between them
           * The divider (1px × 32px) is conditionally rendered for
           * i > 0 so there's no leading divider before the first stat.
           * gap uses clamp() to be responsive — shrinks on mobile.
           */}
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            gap: 'clamp(20px,4vw,48px)', marginBottom: 0,
          }}>
            {[['2.4K+','Beta Signups'],['31','Live Signals'],['Free','To Start']].map(([v,l],i) => (
              <div key={l} style={{ display:'flex', alignItems:'center', gap: 'clamp(20px,4vw,48px)' }}>
                {/* Thin vertical divider between stats */}
                {i > 0 && <div style={{ width:1, height:32, background:'var(--border)' }} />}
                <div style={{ textAlign:'center' }}>
                  <div style={{ fontFamily:'var(--font-display)', fontWeight:800, fontSize:22, color:'var(--text)', letterSpacing:'-0.02em' }}>{v}</div>
                  <div style={{ fontSize:10, color:'var(--text-3)', letterSpacing:'0.08em', textTransform:'uppercase', fontFamily:'var(--font-display)', marginTop:3 }}>{l}</div>
                </div>
              </div>
            ))}
          </div>

        </div>{/* end glassmorphism frame */}
      </div>{/* end max-width wrapper */}

      {/*
       * LAYER 4 — Live ticker strip
       * ─────────────────────────────────────────────────────
       * Absolutely positioned at the bottom of the section.
       * Uses the .ticker-track CSS class (globals.css) which
       * applies the scroll-x animation: translateX(0 → -50%).
       *
       * SEAMLESS LOOP TRICK:
       * TICKER_ITEMS is spread twice [...arr, ...arr] so the
       * second copy starts exactly where the first ends.
       * When the animation reaches -50% (halfway), it's back
       * to the visual start — browser loops seamlessly.
       *
       * backdrop-filter:blur(12px) + semi-transparent background
       * so the gradient shows subtly through the ticker bar.
       *
       * hover pauses the animation (ticker-track:hover in CSS).
       */}
      <div
        role="marquee"
        aria-label="Live market signals"
        style={{
          position:'absolute', bottom:0, left:0, right:0, zIndex:10,
          borderTop:'1px solid var(--border)', background:'rgba(5,8,18,0.88)',
          backdropFilter:'blur(12px)', padding:'9px 0', overflow:'hidden',
        }}
      >
        <div className="ticker-track" style={{ display:'flex', gap:48, width:'max-content' }}>
          {/* First set — readable by screen readers */}
          {TICKER_ITEMS.map((item,i) => (
            <div key={i} style={{ display:'flex', alignItems:'center', gap:8, whiteSpace:'nowrap' }}>
              <span aria-hidden="true" style={{ width:5, height:5, borderRadius:'50%', background:'var(--accent)', flexShrink:0, display:'inline-block' }}/>
              <span style={{ fontSize:11, fontFamily:'var(--font-display)', color:'var(--text-2)', fontWeight:500 }}>{item.label}</span>
              <span style={{ fontSize:11, fontFamily:'var(--font-display)', color:'var(--accent)', fontWeight:700 }}>{item.side} {item.pct}</span>
              <span style={{ fontSize:10, color:'var(--text-3)', fontFamily:'var(--font-display)' }}>{item.heat}</span>
            </div>
          ))}
          {/* Duplicate set — hidden from screen readers, visual loop only */}
          {TICKER_ITEMS.map((item,i) => (
            <div key={`dup-${i}`} aria-hidden="true" style={{ display:'flex', alignItems:'center', gap:8, whiteSpace:'nowrap' }}>
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
