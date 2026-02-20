'use client';
import { useTelegram } from '@/hooks/useTelegram';

export default function FeedCard({ data, index, onTrade, onChat }) {
  const { haptic } = useTelegram();
  const delay = `d${(index % 6) + 1}`;

  const handleTrade = (side, e) => {
    e.stopPropagation();
    haptic.light();
    onTrade?.(data, side);
  };

  const handleChat = (e) => {
    e.stopPropagation();
    haptic.light();
    onChat?.(data);
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

        {/* AI Advice */}
        <div className="advice-wrap">
          <div className="advice-glass">
            <div className="advice-text">{data.advice}</div>
          </div>
          {data.locked ? (
            <div className="advice-lock">
              <button className="lock-btn" onClick={handleChat}>
                Ask OpenClaw · 0.10 USDC
              </button>
            </div>
          ) : (
            <div className="advice-lock" style={{ borderTop: 'none', padding: '0 12px 10px' }}>
              <button className="chip-btn" style={{ width: '100%' }} onClick={handleChat}>
                Chat OpenClaw →
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}