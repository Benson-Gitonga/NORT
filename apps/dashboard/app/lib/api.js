// ─────────────────────────────────────────────────────────────────────────────
// lib/api.js — NORT Dashboard API layer
// All data comes from the FastAPI backend (Neon PostgreSQL on Render).
// NEXT_PUBLIC_API_URL must be set on Vercel to point at the backend.
// ─────────────────────────────────────────────────────────────────────────────

export const BASE = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/$/, '');

// ─── HELPERS ─────────────────────────────────────────────────────────────────

const abbr = (n) => {
  if (n == null) return '—';
  const abs = Math.abs(n);
  if (abs >= 1e9) return (n / 1e9).toFixed(1).replace(/\.0$/, '') + 'B';
  if (abs >= 1e6) return (n / 1e6).toFixed(1).replace(/\.0$/, '') + 'M';
  if (abs >= 1e3) return (n / 1e3).toFixed(1).replace(/\.0$/, '') + 'K';
  return String(Math.round(n));
};

const getStoredWallet = () => {
  if (typeof window === 'undefined') return null;
  try { return window.localStorage.getItem('walletAddress'); }
  catch { return null; }
};

// ─── SIGNALS ─────────────────────────────────────────────────────────────────

export async function getSignals(filter = 'all') {
  // Fetch signals and markets in parallel
  const [sigRes, mktRes] = await Promise.all([
    fetch(`${BASE}/signals/?top=20`),
    fetch(`${BASE}/markets/?limit=100`),
  ]);

  if (!sigRes.ok && !mktRes.ok) throw new Error(`Failed to load feed`);

  // Backend returns a plain array for signals
  const sigData = sigRes.ok ? await sigRes.json() : [];
  const mktData = mktRes.ok ? await mktRes.json() : { markets: [] };

  // Build a lookup map: market_id → market object
  const marketMap = {};
  (mktData.markets || []).forEach(m => { marketMap[m.id] = m; });

  // Signals is a plain array from the backend
  const rawSignals = Array.isArray(sigData) ? sigData : (sigData.signals || []);

  const signals = rawSignals.map(s => {
    const market  = marketMap[s.market_id] || {};
    const heatPct = Math.max(0, Math.min(100, Math.round((s.score || 0) * 100)));
    const status  = heatPct >= 80 ? 'hot' : heatPct >= 50 ? 'warm' : 'cool';
    return {
      id:     s.market_id,
      cat:    market.category || 'Crypto',
      heat:   `${heatPct}° ${status.toUpperCase()}`,
      status,
      q:      market.question || s.reason || 'Unknown market',
      yes:    Math.round((market.current_odds || 0) * 100),
      vol:    abbr(market.volume || 0),
      locked: (s.score || 0) >= 0.7,
      advice: s.reason || '',
    };
  });

  if (filter === 'all') return signals;
  return signals.filter(s => s.status === filter);
}

// ─── MARKETS ─────────────────────────────────────────────────────────────────

export async function getMarket(id) {
  const res = await fetch(`${BASE}/markets/${id}`);
  if (!res.ok) throw new Error(`Market ${id} not found`);
  const m = await res.json();
  return {
    id:     m.id,
    q:      m.question,
    cat:    m.category,
    yes:    Math.round((m.current_odds || 0) * 100),
    vol:    abbr(m.volume || 0),
    status: 'info',
    advice: '',
    locked: false,
  };
}

export async function listMarkets() {
  const res = await fetch(`${BASE}/markets/?limit=100`);
  if (!res.ok) throw new Error(`Markets fetch failed: ${res.status}`);
  const data = await res.json();
  return (data.markets || []).map(m => ({
    id:     m.id,
    q:      m.question,
    cat:    m.category,
    yes:    Math.round((m.current_odds || 0) * 100),
    vol:    abbr(m.volume || 0),
    status: 'info',
    advice: '',
    locked: false,
  }));
}

export async function refreshMarkets() {
  const res = await fetch(`${BASE}/markets/refresh`);
  if (!res.ok) throw new Error(`Refresh failed: ${res.status}`);
  return await res.json();
}

// ─── ADVICE ──────────────────────────────────────────────────────────────────

export async function getAdvice(marketId) {
  const wallet = getStoredWallet();
  const res = await fetch(`${BASE}/agent/advice`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      market_id: String(marketId),
      telegram_id: wallet || null,
      premium: false,
    }),
  });
  if (!res.ok) throw new Error(`Advice fetch failed: ${res.status}`);
  const data = await res.json();
  return {
    summary:    data.summary || '',
    why:        data.why_trending || '',
    risks:      data.risk_factors || [],
    plan:       data.suggested_plan || 'WAIT',
    confidence: data.confidence || 0,
    disclaimer: data.disclaimer || 'Paper trade only. Not financial advice.',
  };
}

export async function getPremiumAdvice(marketId, paymentProof) {
  if (!paymentProof) throw new Error('PAYMENT_REQUIRED');
  const wallet = getStoredWallet();
  const res = await fetch(`${BASE}/agent/advice`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      market_id: String(marketId),
      telegram_id: wallet || null,
      premium: true,
    }),
  });
  if (!res.ok) throw new Error(`Premium advice fetch failed: ${res.status}`);
  const data = await res.json();
  return {
    summary:    data.summary || '',
    why:        data.why_trending || '',
    risks:      data.risk_factors || [],
    plan:       data.suggested_plan || 'WAIT',
    confidence: data.confidence || 0,
    disclaimer: data.disclaimer || 'Paper trade only. Not financial advice.',
  };
}

export async function verifyPayment(proof) {
  if (!proof || proof.length < 4) return { valid: false, error: 'Invalid proof' };
  // x402 verification — proof is accepted if it meets minimum length
  return { valid: true, receipt: `receipt_${Date.now()}` };
}

// ─── PAPER TRADE ─────────────────────────────────────────────────────────────

export async function paperTrade({ marketId, side, amount, price }) {
  const wallet = getStoredWallet();
  let question = '';
  try {
    const m = await getMarket(marketId);
    question = m?.q || '';
  } catch {}

  // Ensure the user/wallet exists in DB before trading
  const userId = (wallet || 'dev_user').toLowerCase();
  try {
    await fetch(`${BASE}/api/wallet/connect`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      // Don't set telegram_id here — it has a UNIQUE constraint and
      // the wallet address is not a real Telegram ID.
      // The wallet_address itself is used as the trading key.
      body:    JSON.stringify({ wallet_address: userId }),
    });
  } catch {}

  // price_per_share must be between 0 and 1 (e.g. 0.55 for 55¢)
  // price coming in may be a percentage (55) or already decimal (0.55)
  const rawPrice = parseFloat(price);
  let normalizedPrice = rawPrice > 1 ? rawPrice / 100 : rawPrice;
  // Clamp to valid range — backend requires strictly between 0 and 1
  normalizedPrice = Math.min(0.99, Math.max(0.01, normalizedPrice));
  // shares = amount / price_per_share, minimum 1, capped to 1 decimal
  const rawAmount = parseFloat(amount);
  if (!rawAmount || rawAmount <= 0) throw new Error('Amount must be greater than 0');
  const computedShares = rawAmount / normalizedPrice;
  const shares = Math.max(1, Math.round(computedShares * 10) / 10);
  // total_cost guard: backend requires >= $1
  const totalCost = Math.round(shares * normalizedPrice * 100) / 100;
  if (totalCost < 1.0) {
    throw new Error('Minimum trade value is $1.00');
  }

  const body = {
    telegram_user_id: userId,
    market_id:        String(marketId),
    market_question:  question || `Market ${marketId}`,
    outcome:          (side || '').toUpperCase() === 'NO' ? 'NO' : 'YES',
    shares,
    price_per_share:  normalizedPrice,
    direction:        'BUY',
  };

  const res = await fetch(`${BASE}/api/papertrade`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify(body),
  });
  if (!res.ok) {
    let detail = '';
    try {
      const errJson = await res.json();
      // FastAPI 422 puts the Pydantic errors in errJson.detail
      detail = JSON.stringify(errJson.detail ?? errJson);
    } catch {}
    console.error('[paperTrade] 422 body sent:', body);
    console.error('[paperTrade] error detail:', detail);
    throw new Error(`Trade failed (${res.status}): ${detail}`);
  }
  const r = await res.json();
  return {
    id:       r.trade_id ?? `t${Date.now()}`,
    marketId,
    side,
    amount,
    price,
    pnl:      0,
    status:   'open',
    ts:       Date.now(),
    txHash:   r.tx_hash || null,
  };
}

// ─── WALLET ──────────────────────────────────────────────────────────────────

export async function getWallet() {
  const wallet = getStoredWallet();
  if (!wallet) return { balance: 0, pnl: 0, pnlPct: 0, trades: 0 };

  const res = await fetch(`${BASE}/api/wallet/summary?wallet_address=${encodeURIComponent(wallet)}`);
  if (!res.ok) throw new Error(`Wallet fetch failed: ${res.status}`);
  const w = await res.json();
  return {
    balance: w.paper_balance       ?? 0,
    pnl:     w.net_pnl             ?? 0,
    pnlPct:  w.net_pnl_pct         ?? 0,
    trades:  w.total_trades        ?? 0,
  };
}

export async function getTrades() {
  const wallet = getStoredWallet();
  if (!wallet) return [];

  const res = await fetch(`${BASE}/api/wallet/summary?wallet_address=${encodeURIComponent(wallet)}`);
  if (!res.ok) throw new Error(`Trades fetch failed: ${res.status}`);
  const w = await res.json();
  return (w.trades || []).map(t => ({
    id:      t.id,
    q:       t.market_question,
    side:    (t.outcome || 'YES').toLowerCase(),
    amount:  Math.round((t.total_cost  || 0) * 100) / 100,
    price:   t.price_per_share || 0,
    status:  (t.status || 'OPEN').toLowerCase(),
    pnl:     t.pnl || 0,
    txHash:  t.tx_hash || null,
  }));
}

export async function commitTrade(tradeId) {
  const res = await fetch(`${BASE}/api/trade/commit`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({ trade_id: tradeId }),
  });
  if (!res.ok) throw new Error(`Commit failed: ${res.status}`);
  const r = await res.json();
  return { ok: true, txHash: r.tx_hash || null };
}

// ─── LEADERBOARD ─────────────────────────────────────────────────────────────

export async function getLeaderboard(limit = 50) {
  const res = await fetch(`${BASE}/api/leaderboard?limit=${limit}`);
  if (!res.ok) throw new Error(`Leaderboard fetch failed: ${res.status}`);
  const data = await res.json();
  return data.leaderboard || [];
}

export async function getMyRank(walletAddress) {
  if (!walletAddress) return null;
  // Always send lowercase — the DB stores wallet addresses lowercased
  const addr = walletAddress.toLowerCase();
  const res = await fetch(`${BASE}/api/leaderboard/me?wallet_address=${encodeURIComponent(addr)}`);
  // 404 = user hasn't traded yet — not an error, just no rank card yet
  if (res.status === 404) return null;
  if (!res.ok) return null;
  return await res.json();
}

// ─── USER STATS & ACHIEVEMENTS ───────────────────────────────────────────────

export async function getUserStats() {
  const wallet = getStoredWallet();
  if (!wallet) return { xp: 0, level: 1, rank: null, streak: 0, xpToNextLevel: 500, xpProgress: 0, totalTrades: 0, winRate: 0 };

  const res = await fetch(`${BASE}/api/user/stats?wallet_address=${encodeURIComponent(wallet)}`);
  if (!res.ok) throw new Error(`User stats fetch failed: ${res.status}`);
  return await res.json();
}

export async function getAchievements() {
  const wallet = getStoredWallet();
  if (!wallet) return [];

  const res = await fetch(`${BASE}/api/user/achievements?wallet_address=${encodeURIComponent(wallet)}`);
  if (!res.ok) throw new Error(`Achievements fetch failed: ${res.status}`);
  const data = await res.json();
  return data.achievements || [];
}
