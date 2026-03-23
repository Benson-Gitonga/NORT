'use client';

const FEATURES = [
  // ── Signals engine — the core of what NORT does ──
  { icon:'solar:bolt-circle-bold',  title:'Real-Time Signals',    desc:'The signals engine scans active Polymarket markets and ranks the most interesting ones by price momentum and volume spikes — before the crowd notices.'  },
  { icon:'solar:fire-bold',         title:'Heat Scoring',         desc:'Every signal is labelled HOT, WARM, or COOL based on momentum and volume anomalies. No guesswork — just real market activity, quantified.'             },
  // ── AI advice — on-demand, separate from signals ──
  { icon:'solar:graph-new-up-bold', title:'AI Market Advice',     desc:'Ask OpenClaw for a plain-English breakdown of any market: key drivers, risks, sentiment, and a suggested position — BUY YES, BUY NO, or WAIT.'         },
  { icon:'solar:bell-bing-bold',    title:'Instant Alerts',       desc:'Get notified the moment a signal hits your thresholds — via Telegram bot or directly in-app. Never miss a fast-moving market.'                           },
  // ── Tools for growth and tracking ──
  { icon:'solar:chart-2-bold',      title:'Performance Tracking', desc:'Track your paper trades, monitor P&L, and see which signals performed across every category. Build your edge with real feedback.'                        },
  { icon:'solar:cup-star-bold',     title:'Leaderboard',          desc:'Compete with other traders on the NORT leaderboard. Rankings update in real time based on portfolio performance and win rate.'                           },
];

export default function Features() {
  return (
    <section id="features" style={{
        padding:'120px 0',
        background:'#000',
        position:'relative',
        overflow:'hidden',
      }}>

      {/* Custom gradient background image — bg-features.png
          Covers the full section, centred, no repeat.
          object-fit:cover equivalent via backgroundSize:cover */}
      <div style={{
        position:'absolute', inset:0, zIndex:0,
        backgroundImage:"url('/images/bg-features.png')",
        backgroundSize:'cover',
        backgroundPosition:'center',
        backgroundRepeat:'no-repeat',
        opacity:0.85,
      }} />

      {/* Dot grid on top of the background image */}
      <div style={{
        position:'absolute', inset:0, zIndex:1, pointerEvents:'none',
        backgroundImage:'radial-gradient(rgba(255,255,255,0.12) 1px, transparent 1px)',
        backgroundSize:'28px 28px',
        maskImage:'radial-gradient(ellipse 90% 90% at 50% 50%, black 30%, transparent 100%)',
        WebkitMaskImage:'radial-gradient(ellipse 90% 90% at 50% 50%, black 30%, transparent 100%)',
      }} />

      <div style={{ maxWidth:1152, margin:'0 auto', padding:'0 24px', position:'relative', zIndex:2 }}>

        {/* Section header */}
        <div className="fade-up" style={{ maxWidth:560, marginBottom:64 }}>
          <span className="pill" style={{ marginBottom:16, display:'inline-flex' }}>Features</span>
          <h2 style={{ fontFamily:'var(--font-display)', fontSize:'clamp(32px,4vw,48px)', fontWeight:800, letterSpacing:'-0.03em', lineHeight:1.05, marginBottom:16 }}>
            Built for prediction<br/>market edge
          </h2>
          <p style={{ fontFamily:'var(--font-body)', fontSize:16, color:'var(--text-2)', lineHeight:1.7 }}>
            A signals engine that ranks markets by real activity, plus an AI layer you can ask for advice. Built for new and experienced Polymarket traders alike.
          </p>
        </div>

        {/* Feature cards grid */}
        <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fit, minmax(300px, 1fr))', gap:16 }}>
          {FEATURES.map((f, i) => (
            <div
              key={f.title}
              className={`feature-card fade-up fade-up-delay-${(i % 3) + 1}`}
            >
              {/* Icon — teal border + teal glow */}
              <div style={{
                width:44, height:44, borderRadius:12, marginBottom:20,
                background:'rgba(255,255,255,0.05)',
                border:'1px solid rgba(0,200,150,0.35)',
                display:'flex', alignItems:'center', justifyContent:'center',
                boxShadow:'0 0 16px rgba(0,200,150,0.15)',
                position:'relative', zIndex:1,
              }}>
                <iconify-icon icon={f.icon} width="22" style={{ color:'var(--accent)' }}></iconify-icon>
              </div>

              <h3 style={{ fontFamily:'var(--font-display)', fontSize:17, fontWeight:700, letterSpacing:'-0.02em', marginBottom:8, color:'var(--text)', position:'relative', zIndex:1 }}>{f.title}</h3>
              <p style={{ fontFamily:'var(--font-body)', fontSize:14, color:'var(--text-2)', lineHeight:1.65, position:'relative', zIndex:1 }}>{f.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
