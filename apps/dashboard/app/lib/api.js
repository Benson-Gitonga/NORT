// ─────────────────────────────────────────────────────────────────────────────
// lib/api.js — NORT Dashboard API layer
// All data comes from the FastAPI backend (Neon PostgreSQL on Render).
// NEXT_PUBLIC_API_URL must be set on Vercel to point at the backend.
// ─────────────────────────────────────────────────────────────────────────────

import { getAccessToken } from '@privy-io/react-auth';

export const BASE = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/$/, '');

// ─── HELPERS ─────────────────────────────────────────────────────────────────

export async function authFetch(endpoint, options = {}) {
  const headers = new Headers(options.headers || {});
  
  // Only attempt to get token client-side
  if (typeof window !== 'undefined') {
    let token = null;
    // Retry poller: Privy's global getAccessToken can randomly return null during rapid mount hydration
    for (let i = 0; i < 4; i++) {
      try {
        token = await getAccessToken();
        if (token) break;
      } catch (e) {
        // silent
      }
      await new Promise(r => setTimeout(r, 250));
    }
    
    if (token) {
      headers.set('Authorization', `Bearer ${token}`);
      // ADDED FOR POSTMAN DEBUGGING:
      console.log(`[DEBUG] Token found! For Postman, use Header:\nAuthorization: Bearer ${token.substring(0, 30)}...`);
      if (typeof window !== 'undefined') window.__DEBUG_TOKEN = token;
    } else {
      console.error("[authFetch] Failed to retrieve Privy token. Token evaluated to null/undefined.");
    }
  }

  let res = await fetch(endpoint, { ...options, headers });
  
  // 1-time retry logic for hydration misses
  if (res.status === 401) {
    console.warn(`[authFetch] 401 Unauthorized on ${endpoint}, checking for stale token...`);
    
    // give Privy exactly 1 attempt to provide a fresh token
    await new Promise(r => setTimeout(r, 500));
    try {
      if (typeof window !== 'undefined') {
        const freshToken = await getAccessToken();
        if (freshToken) headers.set('Authorization', `Bearer ${freshToken}`);
      }
    } catch {}
    
    res = await fetch(endpoint, { ...options, headers });

    // If it STILL fails, the session is dead or backend is blocking it.
    if (res.status === 401) {
      console.error(`[authFetch] FATAL 401 Unauthorized. Dispatching session_expired event.`);
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('session_expired'));
      }
    }
  }
  
  return res;
}

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

export async function getSignals(filter = 'all', category = 'crypto') {
  // category: 'crypto' | 'sports' | 'all'
  const categoryParam = category !== 'all' ? `&category=${category}` : '';
  const sigRes = await authFetch(`${BASE}/signals/?top=50${categoryParam}`);
  if (!sigRes.ok) throw new Error(`Failed to load signals`);

  const sigData = await sigRes.json();
  const rawSignals = Array.isArray(sigData) ? sigData : (sigData.signals || []);

  // Sport categories
  const SPORT_CATS = new Set(['NBA','NHL','Soccer','EPL','La Liga','Serie A','Bundesliga','Ligue 1','UCL','MLB','Tennis','Golf','Sports']);
  const CRYPTO_CATS = new Set(['BTC','ETH','SOL','XRP','HYPE','Crypto']);

  const signals = rawSignals
    .filter(s => {
      if (category === 'crypto') return CRYPTO_CATS.has(s.category || 'Crypto');
      if (category === 'sports') return SPORT_CATS.has(s.category || '');
      return true;
    })
    .map(s => {
      const heatPct = Math.max(0, Math.min(100, Math.round((s.score || 0) * 100)));
      const status  = heatPct >= 80 ? 'hot' : heatPct >= 50 ? 'warm' : 'cool';
      const rawOdds = s.current_odds ?? 0.5;
      const yesInt  = Math.max(1, Math.min(99, Math.round(rawOdds * 100)));

      return {
        id:     s.market_id,
        cat:    s.category || 'Crypto',
        heat:   `${heatPct}° ${status.toUpperCase()}`,
        status,
        q:      s.question || s.reason || 'Unknown market',
        yes:    yesInt,
        vol:    abbr(s.volume || 0),
        locked: (s.score || 0) >= 0.7,
        advice: s.reason || '',
      };
    });

  if (filter === 'all') return signals;
  return signals.filter(s => s.status === filter);
}

// ─── MARKETS ─────────────────────────────────────────────────────────────────

export async function getMarket(id) {
  const res = await authFetch(`${BASE}/markets/${id}`);
  if (!res.ok) throw new Error(`Market ${id} not found`);
  const m = await res.json();
  return {
    id:     m.id,
    q:      m.question,
    cat:    m.category,
    yes:    Math.max(1, Math.min(99, Math.round((m.current_odds || 0.5) * 100))),
    vol:    abbr(m.volume || 0),
    status: 'info',
    advice: '',
    locked: false,
  };
}

export async function listMarkets() {
  const res = await authFetch(`${BASE}/markets/?limit=500`);
  if (!res.ok) throw new Error(`Markets authFetch failed: ${res.status}`);
  const data = await res.json();
  return (data.markets || []).map(m => ({
    id:     m.id,
    q:      m.question,
    cat:    m.category,
    yes:    Math.max(1, Math.min(99, Math.round((m.current_odds || 0.5) * 100))),
    vol:    abbr(m.volume || 0),
    status: 'info',
    advice: '',
    locked: false,
  }));
}

export async function refreshMarkets() {
  const res = await authFetch(`${BASE}/markets/refresh`);
  if (!res.ok) throw new Error(`Refresh failed: ${res.status}`);
  return await res.json();
}

// ─── ADVICE ──────────────────────────────────────────────────────────────────

export async function getAdvice(marketId) {
  const wallet = getStoredWallet();
  const res = await authFetch(`${BASE}/agent/advice`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      market_id: String(marketId),
      telegram_id: wallet || null,
      premium: false,
    }),
  });
  if (!res.ok) throw new Error(`Advice authFetch failed: ${res.status}`);
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

export async function getPremiumAdvice(marketId) {
  const wallet = getStoredWallet();
  const res = await authFetch(`${BASE}/agent/advice`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      market_id: String(marketId),
      telegram_id: wallet || null,
      premium: true,
    }),
  });
  if (res.status === 402) throw new Error('PAYMENT_REQUIRED');
  if (!res.ok) throw new Error(`Premium advice authFetch failed: ${res.status}`);
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

async function verifyPaymentMock(proof) {
  if (!proof || proof.length < 4) return { valid: false, error: 'Invalid proof' };
  // x402 verification — proof is accepted if it meets minimum length
  return { valid: true, receipt: `receipt_${Date.now()}` };
}

// ─── PAPER TRADE ─────────────────────────────────────────────────────────────

export async function paperTrade({ marketId, side, amount, price, question: providedQuestion }) {
  const wallet = getStoredWallet();

  // Use the question passed in directly — it comes from the signal card the user tapped,
  // so it's guaranteed correct. Only fall back to a DB authFetch if nothing was provided.
  let question = providedQuestion || '';
  if (!question) {
    try {
      const m = await getMarket(String(marketId));
      question = m?.q || '';
    } catch {}
  }

  // Ensure the user/wallet exists in DB before trading
  const userId = (wallet || 'dev_user').toLowerCase();
  try {
    await authFetch(`${BASE}/api/wallet/connect`, {
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

  const res = await authFetch(`${BASE}/api/papertrade`, {
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
  if (!wallet) return { balance: 0, pnl: 0, pnlPct: 0, trades: 0, wins: 0, losses: 0, winRate: 0, tradingMode: 'paper' };

  const res = await authFetch(`${BASE}/api/wallet/summary?wallet_address=${encodeURIComponent(wallet)}`);
  if (!res.ok) throw new Error(`Wallet authFetch failed: ${res.status}`);
  const w = await res.json();

  // Use the right balance based on mode
  const isReal = w.trading_mode === 'real';
  return {
    balance:     (isReal ? w.real_balance_usdc : w.paper_balance) ?? 0,
    pnl:         w.net_pnl             ?? 0,
    pnlPct:      w.net_pnl_pct         ?? 0,
    trades:      w.total_trades        ?? 0,
    wins:        w.wins                ?? 0,
    losses:      w.losses              ?? 0,
    winRate:     w.win_rate_pct        ?? 0,
    tradingMode: w.trading_mode        ?? 'paper',
    // keep both balances available
    paperBalance:    w.paper_balance    ?? 0,
    realBalanceUsdc: w.real_balance_usdc ?? 0,
  };
}

export async function getTrades() {
  const wallet = getStoredWallet();
  if (!wallet) return [];

  const res = await authFetch(`${BASE}/api/wallet/summary?wallet_address=${encodeURIComponent(wallet)}`);
  if (!res.ok) throw new Error(`Trades authFetch failed: ${res.status}`);
  const w = await res.json();
  return (w.trades || []).map(t => ({
    id:            t.id,
    marketId:      t.market_id,
    q:             t.market_question,
    side:          (t.outcome || 'YES').toLowerCase(),
    shares:        t.shares || 0,
    amount:        Math.round((t.total_cost || 0) * 100) / 100,
    price:         t.price_per_share || 0,
    currentPrice:  t.current_price ?? null,
    currentValue:  t.current_value ?? null,
    unrealizedPnl: t.unrealized_pnl ?? null,
    status:        (t.status || 'OPEN').toLowerCase(),
    result:        t.result || 'OPEN',
    pnl:           t.pnl ?? 0,
    txHash:        t.tx_hash || null,
  }));
}

export async function getPositionValue(tradeId) {
  const res = await authFetch(`${BASE}/api/trade/value/${tradeId}`);
  if (!res.ok) throw new Error(`Position value authFetch failed: ${res.status}`);
  return await res.json();
}

export async function sellTrade(tradeId) {
  const res = await authFetch(`${BASE}/api/trade/sell/${tradeId}`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
  });
  if (!res.ok) {
    let detail = '';
    try { detail = (await res.json()).detail || ''; } catch {}
    throw new Error(`Sell failed (${res.status}): ${detail}`);
  }
  return await res.json();
}

// ─── LEADERBOARD ─────────────────────────────────────────────────────────────

export async function getLeaderboard(limit = 50, mode = 'paper') {
  const res = await authFetch(`${BASE}/api/leaderboard?limit=${limit}&mode=${mode}`);
  if (!res.ok) throw new Error(`Leaderboard authFetch failed: ${res.status}`);
  const data = await res.json();
  return data.leaderboard || [];
}

export async function getMyRank(walletAddress, mode = 'paper') {
  if (!walletAddress) return null;
  const addr = walletAddress.toLowerCase();
  const res = await authFetch(`${BASE}/api/leaderboard/me?wallet_address=${encodeURIComponent(addr)}&mode=${mode}`);
  // 404 = user hasn't traded yet — not an error, just no rank card yet
  if (res.status === 404) return null;
  if (!res.ok) return null;
  return await res.json();
}

// ─── USER STATS & ACHIEVEMENTS ───────────────────────────────────────────────

export async function getUserStats() {
  const wallet = getStoredWallet();
  if (!wallet) return { xp: 0, level: 1, rank: null, streak: 0, xpToNextLevel: 500, xpProgress: 0, totalTrades: 0, winRate: 0 };

  const res = await authFetch(`${BASE}/api/user/stats?wallet_address=${encodeURIComponent(wallet)}`);
  if (!res.ok) throw new Error(`User stats authFetch failed: ${res.status}`);
  return await res.json();
}

export async function getAchievements() {
  const wallet = getStoredWallet();
  if (!wallet) return [];

  const res = await authFetch(`${BASE}/api/user/achievements?wallet_address=${encodeURIComponent(wallet)}`);
  if (!res.ok) throw new Error(`Achievements authFetch failed: ${res.status}`);
  const data = await res.json();
  return data.achievements || [];
}

// ─── BRIDGE (Phase 2 — LI.FI Base → Polygon) ────────────────────────────────

export async function getBridgeQuote(amountUsdc) {
  const wallet = getStoredWallet();
  if (!wallet) throw new Error('No wallet connected');
  const res = await authFetch(
    `${BASE}/api/bridge/quote?wallet_address=${encodeURIComponent(wallet)}&amount_usdc=${amountUsdc}`
  );
  if (!res.ok) throw new Error(`Bridge quote failed: ${res.status}`);
  return await res.json();
}

export async function startBridge(amountUsdc, lifiTxHash) {
  const wallet = getStoredWallet();
  if (!wallet) throw new Error('No wallet connected');
  const res = await authFetch(`${BASE}/api/bridge/start`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      wallet_address: wallet,
      amount_usdc:    amountUsdc,
      lifi_tx_hash:   lifiTxHash,
    }),
  });
  if (!res.ok) throw new Error(`Bridge start failed: ${res.status}`);
  return await res.json();
}

export async function getBridgeStatus(bridgeId) {
  const res = await authFetch(`${BASE}/api/bridge/status/${bridgeId}`);
  if (!res.ok) throw new Error(`Bridge status failed: ${res.status}`);
  return await res.json();
}

export async function getBridgeHistory() {
  const wallet = getStoredWallet();
  if (!wallet) return { total: 0, bridges: [] };
  const res = await authFetch(
    `${BASE}/api/bridge/history?wallet_address=${encodeURIComponent(wallet)}`
  );
  if (!res.ok) return { total: 0, bridges: [] };
  return await res.json();
}

// ─── PRETIUM (Phase 3 — On-ramp / Off-ramp via Pretium Africa) ──────────────

export async function getPretiumRate(currency = 'KES') {
  const res = await authFetch(`${BASE}/api/pretium/rate?currency=${currency}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Rate authFetch failed: ${res.status}`);
  }
  return await res.json();
}

export async function createOnramp({ amount, phoneNumber, walletAddress, mobileNetwork = 'Safaricom', chain = 'BASE', asset = 'USDC', fee = 0, telegramUserId = null }) {
  const res = await authFetch(`${BASE}/api/pretium/onramp`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      amount: Math.round(amount),
      phone_number: phoneNumber,
      wallet_address: walletAddress,
      mobile_network: mobileNetwork,
      chain,
      asset,
      fee,
      telegram_user_id: telegramUserId,
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `On-ramp failed: ${res.status}`);
  }
  return await res.json();
}

export async function createOfframp({ amountCrypto, phoneNumber, walletAddress, transactionHash, mobileNetwork = 'Safaricom', chain = 'BASE', asset = 'USDC', fee = 0, telegramUserId = null }) {
  const res = await authFetch(`${BASE}/api/pretium/offramp`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      amount_crypto: amountCrypto,
      phone_number: phoneNumber,
      wallet_address: walletAddress,
      transaction_hash: transactionHash,
      mobile_network: mobileNetwork,
      chain,
      asset,
      fee,
      telegram_user_id: telegramUserId,
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Off-ramp failed: ${res.status}`);
  }
  return await res.json();
}

export async function getPretiumTransaction(transactionId) {
  const res = await authFetch(`${BASE}/api/pretium/transaction/${transactionId}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Transaction authFetch failed: ${res.status}`);
  }
  return await res.json();
}

export async function getPretiumTransactions(type = null, limit = 20) {
  const wallet = getStoredWallet();
  if (!wallet) return { transactions: [] };
  let url = `${BASE}/api/pretium/transactions?wallet_address=${encodeURIComponent(wallet)}&limit=${limit}`;
  if (type) url += `&type=${type}`;
  const res = await authFetch(url);
  if (!res.ok) return { transactions: [] };
  return await res.json();
}

export async function getPretiumSettlementAddress(chain = 'BASE') {
  const res = await authFetch(`${BASE}/api/pretium/settlement-address?chain=${chain}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Settlement address authFetch failed: ${res.status}`);
  }
  return await res.json();
}

// ─── REAL BALANCE ─────────────────────────────────────────────────────────────

export async function getFullWallet() {
  const wallet = getStoredWallet();
  if (!wallet) return { paperBalance: 0, realBalanceUsdc: 0, tradingMode: 'paper', pnl: 0, trades: 0 };

  const res = await authFetch(`${BASE}/api/wallet/summary?wallet_address=${encodeURIComponent(wallet)}`);
  if (!res.ok) throw new Error(`Wallet authFetch failed: ${res.status}`);
  const w = await res.json();
  return {
    paperBalance:    w.paper_balance       ?? 0,
    realBalanceUsdc: w.real_balance_usdc   ?? 0,
    tradingMode:     w.trading_mode        ?? 'paper',
    pnl:             w.net_pnl             ?? 0,
    pnlPct:          w.net_pnl_pct         ?? 0,
    trades:          w.total_trades        ?? 0,
    // keep legacy shape too
    balance:         w.paper_balance       ?? 0,
  };
}

export async function verifyPayment(proof, marketId) {
  const wallet = getStoredWallet();
  if (!proof || proof.length < 4) return { valid: false, error: 'Invalid proof' };
  if (!marketId) return { valid: false, error: 'Missing market id' };
  if (!wallet) return { valid: false, error: 'No wallet connected' };

  const res = await authFetch(`${BASE}/x402/verify`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      proof,
      wallet_address: wallet,
      market_id: String(marketId),
    }),
  });

  const data = await res.json();
  if (!res.ok || !data.verified) {
    return { valid: false, error: data.reason || data.detail || 'Verification failed' };
  }

  return { valid: true, receipt: data.tx_hash || proof, details: data };
}
