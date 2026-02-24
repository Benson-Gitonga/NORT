// ─────────────────────────────────────────────────────────────────────────────
// lib/api.js
//
// MOCK API — plug in real endpoints by replacing each function body.
// Set NEXT_PUBLIC_API_URL in .env.local to point at FastAPI backend.
//
// INTERN MAP:
//   getSignals()        → Intern 1 (Markets) + Intern 2 (Signals Engine)
//   getMarket(id)       → Intern 1 (Markets)
//   getAdvice(id)       → Intern 3 (OpenClaw)
//   getPremiumAdvice()  → Intern 3 (OpenClaw) + Intern 4 (x402)
//   verifyPayment()     → Intern 4 (x402)
//   paperTrade()        → Intern 5 (Paper Trading)
//   getWallet()         → Intern 5 (Wallet)
//   getTrades()         → Intern 5 (Paper Trading)
// ─────────────────────────────────────────────────────────────────────────────

const BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const sim  = (ms = 600) => new Promise(r => setTimeout(r, ms));

// ─── MOCK DATA ────────────────────────────────────────────────────────────────

export const MOCK_SIGNALS = [
  {
    id: 1,
    cat: 'Whale',
    heat: '95° HOT',
    status: 'hot',
    q: 'Will BTC hit $100k before Friday\'s close?',
    yes: 67,
    vol: '2.4M',
    locked: true,
    advice: 'Whale volume up 400% on Coinbase. Net long bias confirmed.',
  },
  {
    id: 2,
    cat: 'Momentum',
    heat: '42° WARM',
    status: 'warm',
    q: 'Solana ETF approved by SEC in 2025?',
    yes: 29,
    vol: '890K',
    locked: false,
    advice: 'Regulatory chatter remains bearish. SEC posture unchanged.',
  },
  {
    id: 3,
    cat: 'Volume',
    heat: '78° HOT',
    status: 'hot',
    q: 'Will ETH/BTC ratio flip above 0.065 this week?',
    yes: 51,
    vol: '1.2M',
    locked: true,
    advice: 'ETH outpacing BTC on derivatives flow. Watch 4h RSI.',
  },
  {
    id: 4,
    cat: 'Liquidity',
    heat: '18° COOL',
    status: 'cool',
    q: 'Fed rate cut confirmed for November 2025?',
    yes: 38,
    vol: '3.1M',
    locked: false,
    advice: 'CME futures imply 62% no-cut probability. Macro headwinds persist.',
  },
];

export const MOCK_TRADES = [
  { id: 't1', marketId: 1, q: 'Will BTC hit $100k before Friday\'s close?', side: 'yes', amount: 50, price: 0.67, pnl: 12.40, status: 'open',   ts: Date.now() - 3600000 },
  { id: 't2', marketId: 2, q: 'Solana ETF approved by SEC in 2025?',         side: 'no',  amount: 25, price: 0.71, pnl: -3.20, status: 'open',   ts: Date.now() - 7200000 },
  { id: 't3', marketId: 4, q: 'Fed rate cut confirmed for November 2025?',   side: 'yes', amount: 100, price: 0.38, pnl: 0,    status: 'closed', ts: Date.now() - 86400000 },
];

export const MOCK_WALLET = {
  balance: 428.60,
  pnl: 9.20,
  pnlPct: 2.2,
  trades: MOCK_TRADES.length,
};

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
  try {
    return window.localStorage.getItem('walletAddress');
  } catch {
    return null;
  }
};

// ─── SIGNALS ─────────────────────────────────────────────────────────────────

export async function getSignals(filter = 'all') {
  try {
    const res = await fetch(`${BASE}/signals/?top=20`);
    const data = await res.json();
    const signals = (data.signals || []).map(s => {
      const heatPct = Math.max(0, Math.min(100, Math.round((s.score || 0) * 100)));
      const status = heatPct >= 80 ? 'hot' : heatPct >= 50 ? 'warm' : 'cool';
      return {
        id: s.market_id,
        cat: s.category || 'General',
        heat: `${heatPct}° ${status.toUpperCase()}`,
        status,
        q: s.question || 'Unknown market',
        yes: Math.round((s.current_odds || 0) * 100),
        vol: abbr(s.volume || 0),
        locked: (s.score || 0) >= 0.7,
        advice: s.reason || '',
      };
    });
    if (filter === 'all') return signals;
    return signals.filter(s => s.status === filter);
  } catch (e) {
    if (filter === 'all') return MOCK_SIGNALS;
    return MOCK_SIGNALS.filter(s => s.status === filter);
  }
}

// ─── SINGLE MARKET ───────────────────────────────────────────────────────────
// Intern 1: replace with → fetch(`${BASE}/markets/${id}`)

export async function getMarket(id) {
  try {
    const res = await fetch(`${BASE}/markets/${id}`);
    if (!res.ok) return null;
    const m = await res.json();
    return {
      id: m.id,
      q: m.question,
      cat: m.category,
      yes: Math.round((m.current_odds || 0) * 100),
      vol: abbr(m.volume || 0),
      status: 'info',
      advice: '',
      locked: false,
    };
  } catch {
    return MOCK_SIGNALS.find(s => s.id === id) || null;
  }
}

export async function listMarkets() {
  try {
    const res = await fetch(`${BASE}/markets`);
    const data = await res.json();
    return (data.markets || []).map(m => ({
      id: m.id,
      q: m.question,
      cat: m.category,
      yes: Math.round((m.current_odds || 0) * 100),
      vol: abbr(m.volume || 0),
      status: 'info',
      advice: '',
      locked: false,
    }));
  } catch {
    return MOCK_SIGNALS;
  }
}

export async function refreshMarkets() {
  try {
    const res = await fetch(`${BASE}/markets/refresh`);
    return await res.json();
  } catch {
    return { status: 'error' };
  }
}

// ─── FREE ADVICE (OpenClaw) ───────────────────────────────────────────────────
// Intern 3: replace with → fetch(`${BASE}/agent/advice/${id}`)
// OpenClaw runs ONLY here and in getPremiumAdvice — never on normal signals.

export async function getAdvice(marketId, question) {
  // LIVE: return fetch(`${BASE}/agent/advice/${marketId}`).then(r => r.json());
  await sim(1400);
  return {
    summary: 'Net long bias confirmed across major CEX order books.',
    why: 'Whale wallets moved 18,400 BTC to exchange hot wallets in last 6h.',
    risks: ['Weekend liquidity gap', 'Mt. Gox distribution overhang'],
    plan: 'Small YES position. Set 30% stop. Take profit at 80¢.',
    disclaimer: 'Paper trade only. Not financial advice.',
  };
}

// ─── PREMIUM ADVICE (x402 gated) ─────────────────────────────────────────────
// Intern 3 + 4: x402 receipt checked on backend before OpenClaw runs.

export async function getPremiumAdvice(marketId, paymentProof) {
  // LIVE:
  // return fetch(`${BASE}/agent/premium_advice/${marketId}`, {
  //   method: 'POST',
  //   headers: { 'Content-Type': 'application/json' },
  //   body: JSON.stringify({ proof: paymentProof }),
  // }).then(r => r.json());
  await sim(1800);
  if (!paymentProof) throw new Error('PAYMENT_REQUIRED');
  return {
    summary: 'High conviction YES. Whale accumulation phase active.',
    why: 'Cross-exchange flow data shows 94th percentile buy pressure.',
    risks: ['Flash crash risk', 'Low weekend volume amplifies moves'],
    plan: 'Scale in: 40% now, 40% on any dip to $94k, 20% reserve.',
    levels: { entry: 94000, target: 101500, stop: 90000 },
    disclaimer: 'Paper trade only. Not financial advice.',
  };
}

// ─── x402 PAYMENT VERIFICATION ───────────────────────────────────────────────
// Intern 4: replace with → fetch(`${BASE}/x402/verify`, { method: 'POST', ... })

export async function verifyPayment(proof) {
  // LIVE:
  // return fetch(`${BASE}/x402/verify`, {
  //   method: 'POST',
  //   headers: { 'Content-Type': 'application/json' },
  //   body: JSON.stringify({ proof }),
  // }).then(r => r.json());
  await sim(800);
  // Mock: any non-empty proof string passes
  if (!proof || proof.length < 4) return { valid: false, error: 'Invalid proof' };
  return { valid: true, receipt: `mock_receipt_${Date.now()}` };
}

// ─── PAPER TRADE ─────────────────────────────────────────────────────────────
// Intern 5: replace with → fetch(`${BASE}/papertrade`, { method: 'POST', ... })

export async function paperTrade({ marketId, side, amount, price }) {
  try {
    const wallet = getStoredWallet();
    // Fetch market question for backend schema
    let question = '';
    try {
      const m = await getMarket(marketId);
      question = m?.q || '';
    } catch {}
    const body = {
      telegram_user_id: (wallet || 'dev_user').toLowerCase(),
      market_id: String(marketId),
      market_question: question || `Market ${marketId}`,
      outcome: (side || '').toUpperCase() === 'NO' ? 'NO' : 'YES',
      shares: Math.max(1, Math.round((parseFloat(amount) / price) * 10) / 10),
      price_per_share: price,
      direction: 'BUY',
    };
    const res = await fetch(`${BASE}/api/papertrade`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const r = await res.json();
    return {
      id: r.trade_id ?? `t${Date.now()}`,
      marketId,
      side: side,
      amount: amount,
      price: price,
      pnl: 0,
      status: 'open',
      ts: Date.now(),
      txHash: r.tx_hash || null,
    };
  } catch {
    await sim(400);
    return {
      id: `t${Date.now()}`,
      marketId, side, amount, price,
      pnl: 0,
      status: 'open',
      ts: Date.now(),
      txHash: null,
    };
  }
}

// ─── WALLET SUMMARY ──────────────────────────────────────────────────────────
// Intern 5: replace with → fetch(`${BASE}/wallet/summary`)

export async function getWallet() {
  try {
    const wallet = getStoredWallet();
    if (!wallet) return { balance: 0, pnl: 0, pnlPct: 0, trades: 0 };
    const res = await fetch(`${BASE}/api/wallet/summary?wallet_address=${encodeURIComponent(wallet)}`);
    const w = await res.json();
    return {
      balance: w.paper_balance ?? 0,
      pnl: w.net_pnl ?? 0,
      pnlPct: 0,
      trades: w.total_trades ?? 0,
    };
  } catch {
    return MOCK_WALLET;
  }
}

// ─── MY TRADES ───────────────────────────────────────────────────────────────
// Intern 5: replace with → fetch(`${BASE}/trades`)

export async function getTrades() {
  try {
    const wallet = getStoredWallet();
    if (!wallet) return [];
    const res = await fetch(`${BASE}/api/wallet/summary?wallet_address=${encodeURIComponent(wallet)}`);
    const w = await res.json();
    const trades = (w.trades || []).map(t => ({
      id: t.id,
      q: t.market_question,
      side: (t.outcome || 'YES').toLowerCase(),
      amount: Math.round((t.total_cost || 0) * 100) / 100,
      price: t.price_per_share || 0,
      status: (t.status || 'OPEN').toLowerCase(),
      pnl: t.pnl || 0,
      txHash: t.tx_hash || null,
    }));
    return trades;
  } catch {
    return MOCK_TRADES;
  }
}

export async function commitTrade(tradeId) {
  try {
    const res = await fetch(`${BASE}/api/trade/commit`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ trade_id: tradeId }),
    });
    const r = await res.json();
    return { ok: true, txHash: r.tx_hash || null };
  } catch {
    return { ok: false };
  }
}

// ─── LEADERBOARD ─────────────────────────────────────────────────────────────
<<<<<<< HEAD

export async function getLeaderboard(limit = 50) {
  try {
    const res = await fetch(`${BASE}/api/leaderboard?limit=${limit}`);
    if (!res.ok) throw new Error('fetch failed');
    const data = await res.json();
    return data.leaderboard || [];
  } catch {
    // Mock fallback
    return [
      { rank: 1, display_name: 'whale.eth', portfolio_value: 1842.50, net_pnl: 842.50, net_pnl_pct: 84.25, win_rate: 78, total_trades: 34, streak: 5, xp: 780, badge: { id: 'oracle', label: 'Oracle', emoji: '🔮', color: '#7c3aed' } },
      { rank: 2, display_name: 'degensama', portfolio_value: 1560.00, net_pnl: 560.00, net_pnl_pct: 56.00, win_rate: 65, total_trades: 22, streak: 3, xp: 530, badge: { id: 'shark', label: 'Shark', emoji: '🦈', color: '#0ea5e9' } },
      { rank: 3, display_name: 'nort_user', portfolio_value: 1230.80, net_pnl: 230.80, net_pnl_pct: 23.08, win_rate: 60, total_trades: 15, streak: 1, xp: 265, badge: { id: 'trader', label: 'Trader', emoji: '⚡', color: '#f59e0b' } },
      { rank: 4, display_name: '0xab12...ef34', portfolio_value: 1100.00, net_pnl: 100.00, net_pnl_pct: 10.00, win_rate: 55, total_trades: 8, streak: 0, xp: 130, badge: { id: 'degen', label: 'Degen', emoji: '🎲', color: '#10b981' } },
      { rank: 5, display_name: 'anon999', portfolio_value: 980.00, net_pnl: -20.00, net_pnl_pct: -2.00, win_rate: 40, total_trades: 5, streak: 0, xp: 50, badge: { id: 'degen', label: 'Degen', emoji: '🎲', color: '#10b981' } },
    ];
  }
}

export async function getMyRank(walletAddress) {
  try {
    const res = await fetch(`${BASE}/api/leaderboard/me?wallet_address=${encodeURIComponent(walletAddress)}`);
    if (!res.ok) throw new Error('not found');
    return await res.json();
  } catch {
    return null;
  }
=======
export const MOCK_USER_STATS = {
  xp: 1240,
  level: 5,
  rank: 5,
  streak: 3,
  xpToNextLevel: 260,
  xpProgress: 65,
  totalTrades: 12,
  winRate: 67,
};

export const LB_DATA = {
  pts: [
    { id: 'u1', name: 'cryptoking', av: 'CK', score: '4,820', meta: '32 trades', badges: ['🥇', '🔥', '💎'], isMe: false },
    { id: 'u2', name: 'whale_007', av: 'WH', score: '3,640', meta: '28 trades', badges: ['🐳', '📈'], isMe: false },
    { id: 'u3', name: 'moon_girl', av: 'MG', score: '3,210', meta: '19 trades', badges: ['🌙', '⭐', '🦄'], isMe: false },
    { id: 'u4', name: 'degenape', av: 'DA', score: '2,890', meta: '41 trades', badges: ['🎰', '📝'], isMe: false },
    { id: 'u5', name: 'nortuser', av: 'NJ', score: '1,240', meta: '12 trades', badges: ['🎯', '📈', '⭐'], isMe: true },
    { id: 'u6', name: 'traderbro', av: 'TB', score: '980', meta: '8 trades', badges: ['🎯'], isMe: false },
    { id: 'u7', name: 'satoshi99', av: 'S9', score: '760', meta: '6 trades', badges: ['🎯'], isMe: false },
  ],
  pnl: [
    { id: 'u2', name: 'whale_007', av: 'WH', score: '+$842', meta: '28 trades', sc: 'pos', isMe: false },
    { id: 'u1', name: 'cryptoking', av: 'CK', score: '+$621', meta: '32 trades', sc: 'pos', isMe: false },
    { id: 'u3', name: 'moon_girl', av: 'MG', score: '+$310', meta: '19 trades', sc: 'pos', isMe: false },
    { id: 'u5', name: 'nortuser', av: 'NJ', score: '+$9', meta: '12 trades', sc: 'pos', isMe: true },
    { id: 'u6', name: 'traderbro', av: 'TB', score: '-$42', meta: '8 trades', sc: 'neg', isMe: false },
    { id: 'u4', name: 'degenape', av: 'DA', score: '-$180', meta: '41 trades', sc: 'neg', isMe: false },
    { id: 'u7', name: 'satoshi99', av: 'S9', score: '-$290', meta: '6 trades', sc: 'neg', isMe: false },
  ],
  wr: [
    { id: 'u1', name: 'cryptoking', av: 'CK', score: '84%', meta: '32 trades', isMe: false },
    { id: 'u3', name: 'moon_girl', av: 'MG', score: '79%', meta: '19 trades', isMe: false },
    { id: 'u2', name: 'whale_007', av: 'WH', score: '71%', meta: '28 trades', isMe: false },
    { id: 'u5', name: 'nortuser', av: 'NJ', score: '67%', meta: '12 trades', isMe: true },
    { id: 'u7', name: 'satoshi99', av: 'S9', score: '60%', meta: '6 trades', isMe: false },
    { id: 'u6', name: 'traderbro', av: 'TB', score: '50%', meta: '8 trades', isMe: false },
    { id: 'u4', name: 'degenape', av: 'DA', score: '44%', meta: '41 trades', isMe: false },
  ],
  act: [
    { id: 'u4', name: 'degenape', av: 'DA', score: '41', meta: 'trades placed', isMe: false },
    { id: 'u1', name: 'cryptoking', av: 'CK', score: '32', meta: 'trades placed', isMe: false },
    { id: 'u2', name: 'whale_007', av: 'WH', score: '28', meta: 'trades placed', isMe: false },
    { id: 'u3', name: 'moon_girl', av: 'MG', score: '19', meta: 'trades placed', isMe: false },
    { id: 'u5', name: 'nortuser', av: 'NJ', score: '12', meta: 'trades placed', isMe: true },
    { id: 'u6', name: 'traderbro', av: 'TB', score: '8', meta: 'trades placed', isMe: false },
    { id: 'u7', name: 'satoshi99', av: 'S9', score: '6', meta: 'trades placed', isMe: false },
  ],
  str: [
    { id: 'u1', name: 'cryptoking', av: 'CK', score: '🔥 8', meta: 'current streak', isMe: false },
    { id: 'u3', name: 'moon_girl', av: 'MG', score: '🔥 6', meta: 'current streak', isMe: false },
    { id: 'u2', name: 'whale_007', av: 'WH', score: '🔥 5', meta: 'current streak', isMe: false },
    { id: 'u5', name: 'nortuser', av: 'NJ', score: '🔥 3', meta: 'current streak', isMe: true },
    { id: 'u4', name: 'degenape', av: 'DA', score: '🔥 2', meta: 'current streak', isMe: false },
    { id: 'u6', name: 'traderbro', av: 'TB', score: '🔥 1', meta: 'current streak', isMe: false },
    { id: 'u7', name: 'satoshi99', av: 'S9', score: '—', meta: 'no streak', isMe: false },
  ],
};

export const ACHIEVEMENTS_DATA = [
  { id: 'first', icon: '🎯', name: 'First Trade', desc: 'Complete 1 paper trade', xp: 50, earned: true, isNew: false },
  { id: 'bullish', icon: '📈', name: 'Bullish', desc: 'First profitable trade', xp: 100, earned: true, isNew: false },
  { id: 'vip', icon: '⭐', name: 'VIP', desc: 'Unlock premium advice', xp: 200, earned: true, isNew: true },
  { id: 'moon', icon: '🌙', name: 'Moon Hunter', desc: 'Catch a hot signal & profit', xp: 150, earned: true, isNew: false },
  { id: 'contra', icon: '🦄', name: 'Contrarian', desc: 'Win against majority odds', xp: 250, earned: true, isNew: true },
  { id: 'paper', icon: '📝', name: 'Paper Hands', desc: 'Complete 10 trades', xp: 100, earned: false, isNew: false },
  { id: 'onfire', icon: '🔥', name: 'On Fire', desc: '5-trade winning streak', xp: 300, earned: false, isNew: false },
  { id: 'diamond', icon: '💎', name: 'Diamond Hands', desc: 'Hold until market closes', xp: 200, earned: false, isNew: false },
  { id: 'degen', icon: '🎰', name: 'Degenerate', desc: '10-trade winning streak', xp: 500, earned: false, isNew: false },
  { id: 'whale', icon: '🐳', name: 'Whale', desc: 'Complete 50 trades', xp: 750, earned: false, isNew: false },
];

// Intern 1/5: replace with → fetch(`${BASE}/api/leaderboard`)
export async function getLeaderboard(type = 'pts') {
  try {
    const wallet = getStoredWallet();
    const res = await fetch(`${BASE}/api/wallet/summary?wallet_address=${encodeURIComponent(wallet || '')}`);
    const w = await res.json();
    const trades = w.trades || [];
    const totalTrades = trades.length;
    const closedTrades = trades.filter(t => t.status === 'CLOSED');
    const winningTrades = closedTrades.filter(t => (t.pnl || 0) > 0).length;
    const winRate = totalTrades > 0 ? Math.round((winningTrades / closedTrades.length) * 100) || 0 : 0;
    const netPnl = w.net_pnl || 0;
    const userXp = Math.floor(netPnl * 10) + (totalTrades * 10);
    
    let streak = 0;
    const sortedTrades = [...trades].sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
    for (const t of sortedTrades) {
      if (t.status === 'CLOSED' && (t.pnl || 0) > 0) streak++;
      else if (t.status === 'CLOSED') break;
    }

    const baseData = LB_DATA[type] || LB_DATA.pts;
    const userEntry = {
      id: 'me',
      name: wallet ? wallet.slice(0, 8) : 'you',
      av: wallet ? wallet.slice(2, 4).toUpperCase() : 'YO',
      score: type === 'pts' ? userXp.toLocaleString() : 
             type === 'pnl' ? (netPnl >= 0 ? `+$${netPnl.toFixed(0)}` : `-$${Math.abs(netPnl).toFixed(0)}`) :
             type === 'wr' ? `${winRate}%` :
             type === 'act' ? totalTrades.toString() :
             streak.toString(),
      meta: type === 'act' ? 'trades placed' : 'current streak',
      sc: netPnl > 0 ? 'pos' : netPnl < 0 ? 'neg' : '',
      isMe: true,
      badges: [],
    };

    let combined = [...baseData.filter(d => !d.isMe), userEntry];
    
    if (type === 'pts') {
      combined.sort((a, b) => parseInt(b.score.replace(/,/g, '')) - parseInt(a.score.replace(/,/g, '')));
    } else if (type === 'pnl') {
      combined.sort((a, b) => {
        const aVal = parseFloat(a.score.replace(/[+$]/g, ''));
        const bVal = parseFloat(b.score.replace(/[+$]/g, ''));
        return bVal - aVal;
      });
    } else if (type === 'wr') {
      combined.sort((a, b) => parseInt(b.score) - parseInt(a.score));
    } else if (type === 'act') {
      combined.sort((a, b) => parseInt(b.score) - parseInt(a.score));
    } else if (type === 'str') {
      combined.sort((a, b) => parseInt(b.score || 0) - parseInt(a.score || 0));
    }

    return combined;
  } catch {
    const data = LB_DATA[type];
    return data || LB_DATA.pts;
  }
}

// Intern 5: replace with → fetch(`${BASE}/api/user/stats`)
export async function getUserStats() {
  try {
    const wallet = getStoredWallet();
    if (!wallet) return MOCK_USER_STATS;
    const res = await fetch(`${BASE}/api/wallet/summary?wallet_address=${encodeURIComponent(wallet)}`);
    const w = await res.json();
    const trades = w.trades || [];
    const totalTrades = trades.length;
    const closedTrades = trades.filter(t => t.status === 'CLOSED');
    const winningTrades = closedTrades.filter(t => (t.pnl || 0) > 0).length;
    const winRate = totalTrades > 0 ? Math.round((winningTrades / closedTrades.length) * 100) || 0 : 0;
    const xp = Math.floor((w.net_pnl || 0) * 10) + (totalTrades * 10);
    const level = Math.floor(xp / 500) + 1;
    let streak = 0;
    const sortedTrades = [...trades].sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
    for (const t of sortedTrades) {
      if (t.status === 'CLOSED' && (t.pnl || 0) > 0) streak++;
      else if (t.status === 'CLOSED') break;
    }
    return { xp, level, rank: 0, streak, xpToNextLevel: (level * 500) - xp, xpProgress: (xp % 500) / 5, totalTrades, winRate };
  } catch { return MOCK_USER_STATS; }
}

// Intern 5: replace with → fetch(`${BASE}/api/user/achievements`)
export async function getAchievements() {
  try {
    const wallet = getStoredWallet();
    if (!wallet) return ACHIEVEMENTS_DATA;
    const res = await fetch(`${BASE}/api/wallet/summary?wallet_address=${encodeURIComponent(wallet)}`);
    const w = await res.json();
    const trades = w.trades || [];
    const totalTrades = trades.length;
    const closedTrades = trades.filter(t => t.status === 'CLOSED');
    const netPnl = w.net_pnl || 0;
    let streak = 0;
    const sortedTrades = [...trades].sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
    for (const t of sortedTrades) {
      if (t.status === 'CLOSED' && (t.pnl || 0) > 0) streak++;
      else if (t.status === 'CLOSED') break;
    }
    return ACHIEVEMENTS_DATA.map(a => {
      let earned = false;
      if (a.id === 'first') earned = totalTrades >= 1;
      if (a.id === 'bullish') earned = netPnl > 0;
      if (a.id === 'vip') earned = false;
      if (a.id === 'moon') earned = totalTrades >= 1 && netPnl > 0;
      if (a.id === 'contra') earned = false;
      if (a.id === 'paper') earned = totalTrades >= 10;
      if (a.id === 'onfire') earned = streak >= 5;
      if (a.id === 'diamond') earned = closedTrades.length >= 5;
      if (a.id === 'degen') earned = streak >= 10;
      if (a.id === 'whale') earned = totalTrades >= 50;
      return { ...a, earned };
    });
  } catch { return ACHIEVEMENTS_DATA; }
>>>>>>> cb9d82afafe3ae19e7383359b11d2847e14f3853
}
