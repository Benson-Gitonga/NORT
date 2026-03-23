'use client';

export default function Footer() {
  return (
    <footer style={{ background:'#000', position:'relative', overflow:'hidden' }}>

      {/* Custom gradient background image */}
      <div style={{
        position:'absolute', inset:0, zIndex:0,
        backgroundImage:"url('/images/bg-footer.png')",
        backgroundSize:'cover',
        backgroundPosition:'center',
        backgroundRepeat:'no-repeat',
        opacity:0.9,
      }} />

      {/* Dot grid on top */}
      <div style={{
        position:'absolute', inset:0, zIndex:1, pointerEvents:'none',
        backgroundImage:'radial-gradient(rgba(255,255,255,0.10) 1px, transparent 1px)',
        backgroundSize:'28px 28px',
        maskImage:'radial-gradient(ellipse 90% 90% at 50% 50%, black 30%, transparent 100%)',
        WebkitMaskImage:'radial-gradient(ellipse 90% 90% at 50% 50%, black 30%, transparent 100%)',
      }} />

      <div style={{ padding:'80px 24px', textAlign:'center', position:'relative', overflow:'hidden', zIndex:2 }}>

        <div className="orb" style={{ width:500, height:300, background:'radial-gradient(circle, rgba(0,200,150,0.08) 0%, transparent 70%)', top:'50%', left:'50%', transform:'translate(-50%,-50%)' }}></div>

        <div style={{ position:'relative', zIndex:2 }}>

          

          <h2 style={{ fontFamily:'var(--font-display)', fontSize:'clamp(28px,5vw,56px)', fontWeight:800, letterSpacing:'-0.04em', color:'var(--text)', marginBottom:16 }}>
            Polymarket trading,<br/>made easy
          </h2>

          <p style={{ fontFamily:'var(--font-body)', fontSize:16, color:'var(--text-2)', maxWidth:440, margin:'0 auto 36px' }}>
            Start your trading journey with NORT today
          </p>

          <div style={{ display:'flex', gap:12, justifyContent:'center', flexWrap:'wrap' }}>
            <a href="https://nort-rho.vercel.app" className="btn btn-primary">
              Start Trading Free
              <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 12h14m0 0l-7-7m7 7l-7 7"/>
              </svg>
            </a>
            <a href="https://docs.nortapp.online/" target="_blank" rel="noopener noreferrer" className="btn btn-ghost">Read the Docs</a>
          </div>

          
        </div>
      </div>

      <div style={{ borderTop:'1px solid rgba(255,255,255,0.07)', padding:'20px 24px', position:'relative', zIndex:2 }}>
        <div style={{ maxWidth:1152, margin:'0 auto', display:'flex', flexWrap:'wrap', gap:16, alignItems:'center', justifyContent:'space-between' }}>

          <span className="nav-logo" style={{ fontSize:15 }}>NORT</span>

          <p style={{ fontSize:12, color:'var(--text-3)' }}>© 2026 NORT. All rights reserved.</p>

          <div style={{ display:'flex', gap:20 }}>
            <a href="https://docs.nortapp.online/" target="_blank" rel="noopener noreferrer" className="nav-link" style={{ fontSize:12 }}>Docs</a>
            <a href="https://github.com/Benson-Gitonga/NORT" target="_blank" rel="noopener noreferrer" className="nav-link" style={{ fontSize:12 }}>GitHub</a>
          </div>
        </div>
      </div>

    </footer>
  );
}
