'use client';
import { useState } from 'react';
import Link from 'next/link';
import { useTelegram } from '@/hooks/useTelegram';
import { useAuth } from '@/hooks/useAuth';
import AuthRequiredModal from './AuthRequiredModal';

export default function FeedCard({ data, index, onTrade }) {
  const { haptic } = useTelegram();
  const { isAuthed, login } = useAuth();
  const delay = `d${(index % 6) + 1}`;
  const [copied, setCopied] = useState(false);
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [pendingSide, setPendingSide] = useState(null);

  const handleTrade = (side, e) => {
    e.preventDefault();
    e.stopPropagation();
    haptic.light();
    if (!isAuthed) {
      setPendingSide(side);
      setShowAuthModal(true);
      return;
    }
    onTrade?.(data, side);
  };

  const handleLogin = () => {
    login();
    setShowAuthModal(false);
  };

  const handleCopyId = (e) => {
    e.preventDefault();
    e.stopPropagation();
    haptic.light();
    navigator.clipboard.writeText(data.id).then(() => {
      setCopied(true);
      haptic.success?.();
      setTimeout(() => setCopied(false), 2000);
    });
  };

  return (
    <>
      <Link href={`/market/${data.id}`} className="card-link" style={{ textDecoration: 'none' }}>
        <div className={`scard fu ${delay}`} style={{ minHeight: 'auto' }}>
          <div className={`scard-bar ${data.status}`} />

          <div className="scard-inner" style={{ padding: '16px 20px' }}>
            {/* Meta Row */}
            <div className="scard-meta" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span className="scard-cat" style={{ borderColor: 'rgba(52, 192, 127, 0.4)', color: '#34C07F', background: 'rgba(52, 192, 127, 0.08)', borderRadius: '100px', fontSize: '9px', padding: '3px 10px' }}>
                  {data.cat?.toUpperCase()}
                </span>
                <div onClick={handleCopyId} style={{ display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer', opacity: 0.5, color: '#fff' }}>
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
                  <span style={{ fontSize: '10px', fontFamily: 'DM Mono' }}>{data.id || 'mkt-ID'}</span>
                </div>
              </div>
              
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div className="scard-heat hot" style={{ fontWeight: 800, fontSize: '9px', letterSpacing: '0.05em' }}>HOT</div>
                <div className="scard-close" style={{ fontSize: '9px', color: 'rgba(255,255,255,0.4)' }}>Closes {data.closesIn || 'Jun 23'}</div>
              </div>
            </div>

            {/* Question */}
            <div className="scard-q" style={{ fontSize: '16px', fontWeight: 600, letterSpacing: '-0.01em', marginBottom: '2px', lineHeight: 1.3 }}>
              {data.q}
            </div>
            
            {/* Chance */}
            <div style={{ color: '#34C07F', fontSize: '10px', fontFamily: 'DM Mono', marginBottom: '10px' }}>
              {data.yes}% chance
            </div>

            {/* Odds bar */}
            <div className="odds-wrap">
              <div className="odds-bar-track" style={{ height: '3px', background: 'rgba(255,255,255,0.08)' }}>
                <div className="odds-bar-fill" style={{ 
                  width: `${data.yes}%`, 
                  background: 'linear-gradient(90deg, #34C07F 0%, #0066FF 100%)',
                  boxShadow: '0 0 12px rgba(52, 192, 127, 0.3)'
                }} />
              </div>
              <div className="odds-labels" style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', marginTop: '10px', fontFamily: 'DM Mono' }}>
                <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
                  <span style={{ color: '#34C07F', fontWeight: 600 }}>YES {data.yes}¢</span>
                  <span style={{ color: 'rgba(255,255,255,0.3)', fontSize: '9px' }}>{data.vol || '2.1m'} vol.</span>
                </div>
                <span style={{ color: '#34C07F', fontWeight: 600 }}>NO {100 - data.yes}¢</span>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="bet-row" style={{ marginTop: '14px', display: 'flex', gap: '10px' }}>
              <button className="buy-yes-btn" onClick={(e) => handleTrade('yes', e)} style={{ flex: 1, padding: '8px 0', fontSize: '10px' }}>
                BUY YES
              </button>
              <button className="buy-no-btn" onClick={(e) => handleTrade('no', e)} style={{ flex: 1, padding: '8px 0', fontSize: '10px' }}>
                BUY NO
              </button>
            </div>
          </div>
        </div>
      </Link>

      {showAuthModal && (
        <AuthRequiredModal
          title="Connect to Trade"
          message={`Connect your wallet to place a ${pendingSide?.toUpperCase()} trade on this market.`}
          onLogin={handleLogin}
          onDismiss={() => setShowAuthModal(false)}
        />
      )}
    </>
  );
}
