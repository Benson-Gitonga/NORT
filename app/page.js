/**
 * page.js
 * ─────────────────────────────────────────────
 * The home page. Assembles all section components
 * in the correct order top-to-bottom.
 *
 * Sections (in order):
 *  1. ScrollAnimations — invisible, runs the IntersectionObserver
 *  2. Navbar           — fixed top nav
 *  3. Hero             — headline, CTA, signal dashboard preview, ticker
 *  4. Features         — 6-card feature grid
 *  5. HowItWorks       — 3-step walkthrough with UI previews
 *  6. NortBot          — Spline 3D robot + live chat UI
 *  7. Pricing          — 3 tier cards with monthly/hourly toggle
 *  8. Footer           — final CTA, links, copyright
 *
 * To reorder: move the components below.
 * To hide a section: comment it out.
 * ─────────────────────────────────────────────
 */
import Navbar         from './components/Navbar';
import Hero           from './components/Hero';
import Features       from './components/Features';
import HowItWorks     from './components/HowItWorks';
import NortBot        from './components/NortBot';
import Pricing        from './components/Pricing';
import Footer         from './components/Footer';
import ScrollAnimations from './components/ScrollAnimations';

export default function Home() {
  return (
    <>
      {/* ScrollAnimations: invisible — runs the IntersectionObserver
          that triggers .fade-up animations as elements scroll into view. */}
      <ScrollAnimations />

      {/* Fixed pill navbar — always visible at the top */}
      <Navbar />

      <main id="main-content">
        {/* 1. Hero: full-screen intro, dashboard preview, live ticker */}
        <Hero />

        {/* 2. Features: 6-card grid — what NORT does */}
        <Features />

        {/* 3. How It Works: 3-step walkthrough with signal/analysis/trade previews */}
        <HowItWorks />

        {/* 4. NortBot: Spline 3D robot (left) + interactive chat UI (right) */}
        <NortBot />

        {/* 5. Pricing: Free / Pro / Elite with monthly↔hourly toggle */}
        <Pricing />
      </main>

      {/* Footer: CTA block + links + copyright */}
      <Footer />
    </>
  );
}
