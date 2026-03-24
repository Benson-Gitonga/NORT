'use client';
import { useEffect } from 'react';

export default function LandingScrollAnimations() {
  useEffect(() => {
    const els = document.querySelectorAll('.l-fade-up');
    const observer = new IntersectionObserver(
      entries => entries.forEach(e => { if (e.isIntersecting) e.target.classList.add('visible'); }),
      { threshold: 0.08, rootMargin: '0px 0px -40px 0px' }
    );
    els.forEach(el => observer.observe(el));
    return () => observer.disconnect();
  }, []);
  return null;
}
