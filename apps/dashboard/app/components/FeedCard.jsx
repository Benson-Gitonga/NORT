'use client';
import { useState } from 'react';
import { useTelegram } from '@/hooks/useTelegram';

export default function FeedCard({ data, index, onTrade }) {
  const { haptic } = useTelegram();
  const delay = `d${(index % 6) + 1}`;
  const [copied, setCopied] = useState(false);

  const handleTrade = (side, e) => {
    e.stopPropagation();
    haptic.light();
    onTrade?.(data, side);
  };

  const handleCopyId = (e) => {
    e.stopPropagation();
    haptic.light();
    navigator.clipboard.writeText(data.id).then(() => {
      setCopied(true);
      haptic.success?.();
      setTimeout(() => setCopied(false), 2000);
    }).catch(() => {
      // Fallback for environments where clipboard API isn't available
      const el = document.createElement('textarea');
      el.value = data.id;
      el.style.position = 'fixed';
      el.style.opacity = '0';
      document.body.appendChild(el);
      el.select();
      document.execCommand('copy');
      document.body.removeChild(el);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  return (
    <div className={`scard fu ${delay}`}>
      <div className={`scard-bar ${data.status}`} />

      <div className="scard-inner">
        {/* Meta */}
        <div className="scard-meta">
          <span className="scard-cat">{data.cat}</span>
          <span className={`scard-heat ${data.status}`}>◆ {data.heat}</span>
        </div>

        {/* Question */}
        <div className="scard-q">{data.q}</div>

        {/* Odds bar */}
        <div className="odds-wrap">
          <div className="odds-bar-track">
            <div className="odds-bar-fill" style={{ width: `${data.yes}%` }} />
          </div>
          <div className="odds-labels">
            <span className="odds-yes">YES {data.yes}¢</span>
            <span className="odds-vol">${data.vol} vol</span>
            <span className="odds-no">NO {100 - data.yes}¢</span>
          </div>
        </div>

        {/* Bet buttons */}
        <div className="bet-row">
          <button className="bet-btn" onClick={(e) => handleTrade('yes', e)}>▲ Bet YES</button>
          <button className="bet-btn" onClick={(e) => handleTrade('no', e)}>▼ Bet NO</button>
        </div>

        {/* Market ID copy button */}
        <button
          className={`market-id-btn ${copied ? 'copied' : ''}`}
          onClick={handleCopyId}
        >
          <span className="market-id-label">ID</span>
          <span className="market-id-value">{data.id}</span>
          <span className="market-id-action">{copied ? '✓ Copied' : '⎘ Copy'}</span>
        </button>
      </div>
    </div>
  );
}