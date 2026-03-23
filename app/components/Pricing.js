'use client';

/*
 * ─────────────────────────────────────────────────────────────────────────────
 * PRICING SECTION — v1 (current) + v2 x402 (coming soon)
 * ─────────────────────────────────────────────────────────────────────────────
 *
 * CURRENT STATE (v1):
 *   - Single Free card, centred on the page.
 *   - Pro / x402 card shown but greyed out as "Coming in v2".
 *   - No toggle (billing period toggle removed — no paid tiers in v1).
 *
 * WHEN v2 x402 IS READY — switch to the commented block below:
 *   1. Remove the current two-card grid and the commented block below it.
 *   2. Uncomment the <!-- V2 ACTIVE PRICING --> section.
 *   3. The toggle switches between per-query ($0.10 USDC) and monthly views.
 *   4. Pro card becomes fully clickable with a live CTA.
 *
 * x402 PAYMENT FLOW (for whoever implements):
 *   - User hits /premium_advice → server returns 402 + treasury address
 *   - User sends 0.10 USDC on Base → gets a tx hash
 *   - User sends /pay <tx_hash> → backend calls POST /x402/verify
 *   - Verifier checks: recipient, amount, no replay → unlocks premium advice
 *   - Automated flow: X-Payment header with EIP-712 signed auth (stretch goal)
 *   - Payments stay on Base — never cross-chain, independent of trade flow
 *
 * ─────────────────────────────────────────────────────────────────────────────
 */

const FEATURES_FREE = [
  'Full access to crypto & sports markets',
  'Real-time signal scoring (HOT / WARM / COOL)',
  'AI market analysis via OpenClaw',
  '$1,000 paper USDC starting balance',
  'Paper trading with P&L tracking',
  'Leaderboard, XP & achievements',
  'Telegram bot + Mini App access',
];

const FEATURES_PRO = [
  'Everything in Free',
  'Premium AI advice via x402',
  '$0.10 USDC per query — pay only when you use it',
  'No subscriptions, no API keys',
  'Payments settle on Base — instant, on-chain',
  'Automated client support (X-Payment header)',
  'Early access to v2 features',
];


export default function Pricing() {
  return (
    <section id="pricing" style={{ padding:'120px 0', background:'#000', position:'relative', overflow:'hidden' }}>

      {/* bg-pricing background image */}
      <div style={{
        position:'absolute', inset:0, zIndex:0,
        backgroundImage:"url('/images/bg-pricing.png')",
        backgroundSize:'cover',
        backgroundPosition:'center',
        backgroundRepeat:'no-repeat',
        opacity:0.85,
      }} />

      {/* Dot grid */}
      <div style={{
        position:'absolute', inset:0, zIndex:1, pointerEvents:'none',
        backgroundImage:'radial-gradient(rgba(255,255,255,0.1) 1px, transparent 1px)',
        backgroundSize:'28px 28px',
        maskImage:'radial-gradient(ellipse 90% 90% at 50% 50%, black 30%, transparent 100%)',
        WebkitMaskImage:'radial-gradient(ellipse 90% 90% at 50% 50%, black 30%, transparent 100%)',
      }} />

      <div style={{ maxWidth:1152, margin:'0 auto', padding:'0 24px', position:'relative', zIndex:2 }}>

        {/* Header */}
        <div className="fade-up" style={{ textAlign:'center', marginBottom:56 }}>
          <span className="pill" style={{ marginBottom:16, display:'inline-flex' }}>Pricing</span>
          <h2 style={{ fontFamily:'var(--font-display)', fontSize:'clamp(32px,4vw,48px)', fontWeight:800, letterSpacing:'-0.03em', lineHeight:1.05, marginBottom:16 }}>
            Free while in beta
          </h2>
          <p style={{ fontFamily:'var(--font-body)', fontSize:15, color:'var(--text-2)', maxWidth:480, margin:'0 auto' }}>
            NORT v1 is fully free — no card required. Everything below is included from day one.
          </p>
        </div>


        {/* ── CURRENT: v1 layout — Free card centred, Pro greyed out ─────────────
            When v2 x402 is ready, remove this block and uncomment V2 ACTIVE below
        ─────────────────────────────────────────────────────────────────────── */}
        <div style={{ display:'flex', justifyContent:'center' }}>
          <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fit, minmax(300px, 1fr))', gap:16, width:'100%', maxWidth:740 }}>

            {/* FREE card */}
            <div className="fade-up fade-up-delay-1" style={{
              display:'flex', flexDirection:'column',
              background:`radial-gradient(50% 50% at 0% 0%, rgba(0,200,150,0.16) 0%, rgba(26,159,175,0.08) 40%, transparent 100%),
                          radial-gradient(50% 50% at 100% 100%, rgba(26,127,232,0.12) 0%, transparent 100%),
                          rgba(255,255,255,0.04)`,
              backdropFilter:'blur(20px)', WebkitBackdropFilter:'blur(20px)',
              border:'1px solid rgba(0,200,150,0.25)',
              borderRadius:20, padding:32, position:'relative', overflow:'hidden',
              boxShadow:'0 0 40px rgba(0,200,150,0.06), inset 0 1px 0 rgba(255,255,255,0.08)',
            }}>
              <div style={{ position:'absolute', inset:'0 0 auto 0', height:1, background:'linear-gradient(90deg, transparent, var(--accent), transparent)' }} />
              <span className="pill pill-accent" style={{ fontSize:10, display:'inline-flex', marginBottom:20, width:'fit-content' }}>Current version</span>
              <div style={{ display:'flex', alignItems:'baseline', gap:4, marginBottom:8 }}>
                <span style={{ fontFamily:'var(--font-display)', fontSize:52, fontWeight:800, color:'var(--text)', letterSpacing:'-0.04em', lineHeight:1 }}>$0</span>
                <span style={{ fontFamily:'var(--font-display)', fontSize:13, color:'var(--text-3)' }}>/ forever</span>
              </div>
              <p style={{ fontFamily:'var(--font-body)', fontSize:13, color:'var(--text-2)', lineHeight:1.6, marginBottom:28 }}>
                Full access to everything in NORT v1. Start with a $1,000 paper USDC wallet and trade immediately.
              </p>
              <ul style={{ flex:1, listStyle:'none', marginBottom:28, display:'flex', flexDirection:'column', gap:12 }}>
                {FEATURES_FREE.map((f) => (
                  <li key={f} style={{ display:'flex', alignItems:'center', gap:10, fontSize:13, color:'var(--text-2)' }}>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round">
                      <path d="M5 13l4 4L19 7"/>
                    </svg>
                    {f}
                  </li>
                ))}
              </ul>
              <a href="https://nort-rho.vercel.app" className="btn btn-primary" style={{ width:'100%', justifyContent:'center', borderRadius:10 }}>
                Start Trading Free
              </a>
            </div>


            {/* PRO · x402 card — greyed out until v2 ships */}
            <div className="fade-up fade-up-delay-2" style={{
              display:'flex', flexDirection:'column',
              background:`radial-gradient(50% 50% at 0% 0%, rgba(26,127,232,0.10) 0%, transparent 60%), rgba(255,255,255,0.02)`,
              backdropFilter:'blur(20px)', WebkitBackdropFilter:'blur(20px)',
              border:'1px solid rgba(255,255,255,0.07)',
              borderRadius:20, padding:32, position:'relative', overflow:'hidden',
              opacity:0.65,
            }}>
              <span className="pill" style={{ fontSize:10, display:'inline-flex', marginBottom:20, width:'fit-content' }}>Coming in v2</span>
              <div style={{ display:'flex', alignItems:'baseline', gap:4, marginBottom:8 }}>
                <span style={{ fontFamily:'var(--font-display)', fontSize:52, fontWeight:800, color:'var(--text)', letterSpacing:'-0.04em', lineHeight:1 }}>$0.10</span>
                <span style={{ fontFamily:'var(--font-display)', fontSize:13, color:'var(--text-3)' }}>USDC / query</span>
              </div>
              <p style={{ fontFamily:'var(--font-body)', fontSize:13, color:'var(--text-2)', lineHeight:1.6, marginBottom:28 }}>
                Pay per premium advice query via x402. No subscription, no API keys — just on-chain proof on Base.
              </p>
              <ul style={{ flex:1, listStyle:'none', marginBottom:28, display:'flex', flexDirection:'column', gap:12 }}>
                {FEATURES_PRO.map((f) => (
                  <li key={f} style={{ display:'flex', alignItems:'center', gap:10, fontSize:13, color:'var(--text-3)' }}>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--text-3)" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round">
                      <path d="M5 13l4 4L19 7"/>
                    </svg>
                    {f}
                  </li>
                ))}
              </ul>
              <div className="btn btn-ghost" style={{ width:'100%', justifyContent:'center', borderRadius:10, opacity:0.5, cursor:'not-allowed', pointerEvents:'none' }}>
                Coming Soon
              </div>
            </div>

          </div>
        </div>
        {/* ── END v1 layout ─────────────────────────────────────────────────── */}


        {/*
        ── V2 ACTIVE PRICING — uncomment this entire block when x402 ships ──────
        ── and delete the v1 layout block above ─────────────────────────────────

        <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fit, minmax(300px, 1fr))', gap:16, maxWidth:740, margin:'0 auto' }}>

          FREE card — same as above, no changes needed

          PRO card — replace the greyed-out version with this:
          <div className="fade-up fade-up-delay-2" style={{
            display:'flex', flexDirection:'column',
            background:`radial-gradient(50% 50% at 0% 0%, rgba(26,127,232,0.18) 0%, rgba(26,159,175,0.10) 40%, transparent 100%),
                        radial-gradient(50% 50% at 100% 100%, rgba(26,127,232,0.14) 0%, transparent 100%),
                        rgba(255,255,255,0.05)`,
            backdropFilter:'blur(20px)', WebkitBackdropFilter:'blur(20px)',
            border:'1px solid rgba(26,127,232,0.3)',
            borderRadius:20, padding:32, position:'relative', overflow:'hidden',
            boxShadow:'0 0 40px rgba(26,127,232,0.06), inset 0 1px 0 rgba(255,255,255,0.08)',
          }}>
            <div style={{ position:'absolute', inset:'0 0 auto 0', height:1, background:'linear-gradient(90deg, transparent, var(--blue), transparent)' }} />
            <span className="pill" style={{ fontSize:10, display:'inline-flex', marginBottom:20, width:'fit-content', borderColor:'rgba(26,127,232,0.3)', background:'rgba(26,127,232,0.1)', color:'var(--blue)' }}>x402 · Base</span>
            <div style={{ display:'flex', alignItems:'baseline', gap:4, marginBottom:8 }}>
              <span style={{ fontFamily:'var(--font-display)', fontSize:52, fontWeight:800, color:'var(--text)', letterSpacing:'-0.04em', lineHeight:1 }}>$0.10</span>
              <span style={{ fontFamily:'var(--font-display)', fontSize:13, color:'var(--text-3)' }}>USDC / query</span>
            </div>
            <p style={{ fontFamily:'var(--font-body)', fontSize:13, color:'var(--text-2)', lineHeight:1.6, marginBottom:28 }}>
              Pay per premium advice query via x402. No subscription, no API keys — just on-chain proof on Base.
            </p>
            <ul style={{ flex:1, listStyle:'none', marginBottom:28, display:'flex', flexDirection:'column', gap:12 }}>
              {FEATURES_PRO.map((f) => (
                <li key={f} style={{ display:'flex', alignItems:'center', gap:10, fontSize:13, color:'var(--text-2)' }}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--blue)" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round">
                    <path d="M5 13l4 4L19 7"/>
                  </svg>
                  {f}
                </li>
              ))}
            </ul>
            <a href="https://nort-rho.vercel.app" className="btn" style={{ width:'100%', justifyContent:'center', borderRadius:10, background:'linear-gradient(135deg, var(--blue), #0057CC)', color:'#fff', boxShadow:'0 0 24px rgba(26,127,232,0.3)' }}>
              Get Premium Access
            </a>
          </div>

        </div>
        ── END V2 ACTIVE PRICING ─────────────────────────────────────────────── */}

        {/* Beta disclaimer */}
        <p className="fade-up" style={{ textAlign:'center', marginTop:32, fontFamily:'var(--font-body)', fontSize:13, color:'var(--text-3)' }}>
          NORT v1 is paper trading only — no real funds are ever moved.{' '}
          <a href="https://docs.nortapp.online/" target="_blank" rel="noopener noreferrer" style={{ color:'var(--accent)', textDecoration:'none' }}>Read the docs →</a>
        </p>

      </div>
    </section>
  );
}
