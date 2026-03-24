'use client';
import './landing.css';
import LandingNavbar      from './components/LandingNavbar';
import Hero               from './components/Hero';
import Features           from './components/Features';
import HowItWorks         from './components/HowItWorks';
import NortBot            from './components/NortBot';
import Pricing            from './components/Pricing';
import LandingFooter      from './components/Footer';
import LandingScrollAnimations from './components/ScrollAnimations';

export default function LandingPage() {
  return (
    <div className="landing-root">
      <LandingScrollAnimations />
      <LandingNavbar />
      <main id="main-content">
        <Hero />
        <Features />
        <HowItWorks />
        <NortBot />
        <Pricing />
      </main>
      <LandingFooter />
    </div>
  );
}
