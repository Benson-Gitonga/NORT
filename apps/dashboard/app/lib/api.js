// ─────────────────────────────────────────────────────────────────────────────
// lib/api.js — NORT API layer
//
// FIX: getAccessToken does NOT exist as a standalone Privy import.
// It only exists on the usePrivy() hook return value.
// We use TokenStore (populated by PrivyProvidersInner on mount) to access it.
//
// FIX: Backend get_current_user also needs X-Wallet-Address because
// Privy access tokens do not embed wallet addresses in their payload.
// ─────────────────────────────────────────────────────────────────────────────

import { TokenStore } from './tokenStore';

export const BASE = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/$/, '');

// ─── SESSION EXPIRED EVENT ───────────────────────────────────────────────────
function dispatchSessionExpired() {
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent('session_expired'));
  }
}

// ─── TOKEN FETCHER ────────────────────────────────────────────────────────────
async function getToken() {
  if (typeof window === 'undefined') return null;

  const getAccessToken = TokenStore.get();
  if (!getAccessToken) {
    // Privy not ready yet — wait up to 2s
    for (let i = 0; i < 10; i++) {
      await new Promise(r => setTimeout(r, 200));
      const fn = TokenStore.get();
      if (fn) return fn().catch(() => null);
    }
    return null;
  }

  return getAccessToken().catch(() => null);
}

const getStoredWallet = () => {
  if (typeof window === 'undefined') return null;
  try { return window.localStorage.getItem('walletAddress'); }
  catch { return null; }
};

const AUTH_STATE_EVENT = 'nort_auth_state';
const SESSION_EXPIRED_EVENT = 'session_expired';
const TOKEN_POLL_ATTEMPTS = 6;
const TOKEN_POLL_DELAY_MS = 200;
const AUTH_READY_TIMEOUT_MS = 4000;

let accessTokenCache = null;
let accessTokenCachedAt = 0;
let sessionExpiredNotified = false;

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const isValidToken = (token) =>
  !!token && token !== 'null' && token !== 'undefined' && token.split('.').length === 3;

const buildUnauthorizedResponse = (detail = 'Unauthorized') =>
  new Response(JSON.stringify({ detail }), {
    status: 401,
    headers: { 'Content-Type': 'application/json' },
  });

const getAuthState = () => {
  if (typeof window === 'undefined') return { ready: false, isAuthed: false };
  return window.__NORT_AUTH_STATE || { ready: false, isAuthed: false };
};

const notifySessionExpired = (reason, endpoint, status = 401) => {
  if (typeof window === 'undefined' || sessionExpiredNotified) return;
  sessionExpiredNotified = true;
  window.dispatchEvent(new CustomEvent(SESSION_EXPIRED_EVENT, {
    detail: { reason, endpoint, status, at: Date.now() },
  }));
};

const waitForAuthReady = async (timeoutMs = AUTH_READY_TIMEOUT_MS) => {
  if (typeof window === 'undefined') return { ready: false, isAuthed: false };
  const current = getAuthState();
  if (current.ready) return current;

  return new Promise((resolve) => {
    let settled = false;
    const finish = (state) => {
      if (settled) return;
      settled = true;
      window.removeEventListener(AUTH_STATE_EVENT, onAuthState);
      clearTimeout(timer);
      resolve(state || getAuthState());
    };
    const onAuthState = (event) => {
      const detail = event?.detail || getAuthState();
      if (detail.ready) finish(detail);
    };
    const timer = setTimeout(() => finish(getAuthState()), timeoutMs);
    window.addEventListener(AUTH_STATE_EVENT, onAuthState);
  });
};

const resolveAccessToken = async () => {
  const now = Date.now();
  if (isValidToken(accessTokenCache) && (now - accessTokenCachedAt) < 30_000) {
    return accessTokenCache;
  }

  for (let i = 0; i < TOKEN_POLL_ATTEMPTS; i += 1) {
    try {
      const token = await getToken();
      if (isValidToken(token)) {
        accessTokenCache = token;
        accessTokenCachedAt = Date.now();
        sessionExpiredNotified = false;
        return token;
      }
    } catch {}
    await sleep(TOKEN_POLL_DELAY_MS);
  }

  accessTokenCache = null;
  accessTokenCachedAt = 0;
  return null;
};

export async function authFetch(endpoint, options = {}) {
  const {
    requireAuth = true,
    ...requestOptions
  } = options;
  const headers = new Headers(requestOptions.headers || {});
  const walletAddress = getStoredWallet();

  if (walletAddress) {
    headers.set('X-Wallet-Address', walletAddress.toLowerCase());
  }

  if (typeof window === 'undefined') {
    return fetch(endpoint, { ...requestOptions, headers });
  }

  if (requireAuth) {
    const authState = await waitForAuthReady();
    if (!authState.ready || !authState.isAuthed) {
      notifySessionExpired('auth_not_ready_or_not_authed', endpoint, 401);
      return buildUnauthorizedResponse('Authentication required');
    }

    const token = await resolveAccessToken();
    if (!token) {
      notifySessionExpired('missing_privy_access_token', endpoint, 401);
      return buildUnauthorizedResponse('Missing Privy access token');
    }

    headers.set('Authorization', `Bearer ${token}`);
    window.__NORT_LAST_ACCESS_TOKEN = token;
  } else {
    try {
      const optionalToken = await getToken();
      if (isValidToken(optionalToken)) headers.set('Authorization', `Bearer ${optionalToken}`);
    } catch {}
  }

  const res = await fetch(endpoint, { ...requestOptions, headers });
  if (requireAuth && res.status === 401) {
    accessTokenCache = null;
    accessTokenCachedAt = 0;
    notifySessionExpired('backend_rejected_token', endpoint, 401);
  }

  return res;
}

// ─── HELPERS ─────────────────────────────────────────────────────────────────

const abbr = (n) => {
  if (n == null) return '—';
  const abs = Math.abs(n);
  if (abs >= 1e9) return (n / 1e9).toFixed(1).replace(/\.0$/, '') + 'B';
  if (abs >= 1e6) return (n / 1e6).toFixed(1).replace(/\.0$/, '') + 'M';
  if (abs >= 1e3) return (n / 1e3).toFixed(1).replace(/\.0$/, '') + 'K';
  return String(Math.round(n));
};

// ─── SIGNALS ─────────────────────────────────────────────────────────────────

export async function getSignals(filter = 'all', category = 'crypto') {
  const categoryParam = category !== 'all' ? `&category=${category}` : '';
  const sigRes = await authFetch(`${BASE}/signals/?top=50${categoryParam}`, { requireAuth: false });
  if (!sigRes.ok) throw new Error(`Failed to load signals`);

  const sigData = await sigRes.json();
  const rawSignals = Array.isArray(sigData) ? sigData : (sigData.signals || []);

  const SPORT_CATS  = new Set(['NBA','NHL','Soccer','EPL','La Liga','Serie A','Bundesliga','Ligue 1','UCL','MLB','Tennis','Golf','Sports']);
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
      const yesInt  = Math.max(1, Math.min(99, Math.round((s.current_odds ?? 0.5) * 100)));
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

  return filter === 'all' ? signals : signals.filter(s => s.status === filter);
}

// ─── MARKETS ─────────────────────────────────────────────────────────────────

export async function getMarket(id) {
  const res = await authFetch(`${BASE}/markets/${id}`, { requireAuth: false });
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

// market-p: Fetches real YES price history for a market from the backend,
// which in turn calls Polymarket's CLOB API. Returns a plain number array
// (values 0-100) ready to pass directly into SVGLineChart's data prop.
// Falls back to empty array — page.jsx handles the placeholder fallback.
export async function getMarketPriceHistory(id, interval = '1w') {
  try {
    const res = await authFetch(`${BASE}/markets/${id}/price-history?interval=${interval}`);
    if (!res.ok) return [];
    const data = await res.json();
    return data.prices || []; // market-p: flat number array e.g. [48.2, 51.0, 55.3, ...]
  } catch {
    return []; // market-p: silent fail — chart will use placeholder data
  }
}
// ─── end market-p ─────────────────────────────────────────────────────────────

export async function listMarkets() {
  const res = await authFetch(`${BASE}/markets/?limit=500`, { requireAuth: false });
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
  const res = await authFetch(`${BASE}/markets/refresh`, { requireAuth: false });
  if (!res.ok) throw new Error(`Refresh failed: ${res.status}`);
  return await res.json();
}

// ─── ADVICE ──────────────────────────────────────────────────────────────────

export async function getAdvice(marketId) {
  const wallet = getStoredWallet();
  const res = await authFetch(`${BASE}/agent/advice`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ market_id: String(marketId), telegram_id: wallet || null, premium: false }),
  });
  if (!res.ok) throw new Error(`Advice authFetch failed: ${res.status}`);
  const data = await res.json();
  return { summary: data.summary || '', why: data.why_trending || '', risks: data.risk_factors || [], plan: data.suggested_plan || 'WAIT', confidence: data.confidence || 0, disclaimer: data.disclaimer || 'Paper trade only. Not financial advice.' };
}

export async function getPremiumAdvice(marketId) {
  const wallet = getStoredWallet();
  const res = await authFetch(`${BASE}/agent/advice`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ market_id: String(marketId), telegram_id: wallet || null, premium: true }),
  });
  if (res.status === 402) throw new Error('PAYMENT_REQUIRED');
  if (!res.ok) throw new Error(`Premium advice authFetch failed: ${res.status}`);
  const data = await res.json();
  return { summary: data.summary || '', why: data.why_trending || '', risks: data.risk_factors || [], plan: data.suggested_plan || 'WAIT', confidence: data.confidence || 0, disclaimer: data.disclaimer || 'Paper trade only. Not financial advice.' };
}

// ─── PAPER TRADE ─────────────────────────────────────────────────────────────

export async function paperTrade({ marketId, side, amount, price, question: providedQuestion }) {
  const wallet = getStoredWallet();
  let question = providedQuestion || '';
  if (!question) { try { const m = await getMarket(String(marketId)); question = m?.q || ''; } catch {} }

  const userId = (wallet || 'dev_user').toLowerCase();
  try {
    await authFetch(`${BASE}/api/wallet/connect`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ wallet_address: userId }),
    });
  } catch {}

  const rawPrice = parseFloat(price);
  let normalizedPrice = rawPrice > 1 ? rawPrice / 100 : rawPrice;
  normalizedPrice = Math.min(0.99, Math.max(0.01, normalizedPrice));
  const rawAmount = parseFloat(amount);
  if (!rawAmount || rawAmount <= 0) throw new Error('Amount must be greater than 0');
  const shares = Math.max(1, Math.round((rawAmount / normalizedPrice) * 10) / 10);
  const totalCost = Math.round(shares * normalizedPrice * 100) / 100;
  if (totalCost < 1.0) throw new Error('Minimum trade value is $1.00');

  const body = { telegram_user_id: userId, market_id: String(marketId), market_question: question || `Market ${marketId}`, outcome: (side || '').toUpperCase() === 'NO' ? 'NO' : 'YES', shares, price_per_share: normalizedPrice, direction: 'BUY' };
  const res = await authFetch(`${BASE}/api/papertrade`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  if (!res.ok) { let d = ''; try { d = JSON.stringify((await res.json()).detail ?? {}); } catch {} throw new Error(`Trade failed (${res.status}): ${d}`); }
  const r = await res.json();
  return { id: r.trade_id ?? `t${Date.now()}`, marketId, side, amount, price, pnl: 0, status: 'open', ts: Date.now(), txHash: r.tx_hash || null };
}

// ─── WALLET ──────────────────────────────────────────────────────────────────

export async function getWallet() {
  const wallet = getStoredWallet();
  if (!wallet) return { balance: 0, pnl: 0, pnlPct: 0, trades: 0, wins: 0, losses: 0, winRate: 0, tradingMode: 'paper' };
  const res = await authFetch(`${BASE}/api/wallet/summary?wallet_address=${encodeURIComponent(wallet)}`);
  if (!res.ok) throw new Error(`Wallet authFetch failed: ${res.status}`);
  const w = await res.json();
  const isReal = w.trading_mode === 'real';
  return { balance: (isReal ? w.real_balance_usdc : w.paper_balance) ?? 0, pnl: w.net_pnl ?? 0, pnlPct: w.net_pnl_pct ?? 0, trades: w.total_trades ?? 0, wins: w.wins ?? 0, losses: w.losses ?? 0, winRate: w.win_rate_pct ?? 0, tradingMode: w.trading_mode ?? 'paper', paperBalance: w.paper_balance ?? 0, realBalanceUsdc: w.real_balance_usdc ?? 0 };
}

export async function getFullWallet() {
  const wallet = getStoredWallet();
  if (!wallet) return { paperBalance: 0, realBalanceUsdc: 0, tradingMode: 'paper', pnl: 0, trades: 0 };
  const res = await authFetch(`${BASE}/api/wallet/summary?wallet_address=${encodeURIComponent(wallet)}`);
  if (!res.ok) throw new Error(`Wallet authFetch failed: ${res.status}`);
  const w = await res.json();
  return { paperBalance: w.paper_balance ?? 0, realBalanceUsdc: w.real_balance_usdc ?? 0, tradingMode: w.trading_mode ?? 'paper', pnl: w.net_pnl ?? 0, pnlPct: w.net_pnl_pct ?? 0, trades: w.total_trades ?? 0, balance: w.paper_balance ?? 0 };
}

export async function getTrades() {
  const wallet = getStoredWallet();
  if (!wallet) return [];
  const res = await authFetch(`${BASE}/api/wallet/summary?wallet_address=${encodeURIComponent(wallet)}`);
  if (!res.ok) throw new Error(`Trades authFetch failed: ${res.status}`);
  const w = await res.json();
  return (w.trades || []).map(t => ({ id: t.id, marketId: t.market_id, q: t.market_question, side: (t.outcome || 'YES').toLowerCase(), shares: t.shares || 0, amount: Math.round((t.total_cost || 0) * 100) / 100, price: t.price_per_share || 0, currentPrice: t.current_price ?? null, currentValue: t.current_value ?? null, unrealizedPnl: t.unrealized_pnl ?? null, status: (t.status || 'OPEN').toLowerCase(), result: t.result || 'OPEN', pnl: t.pnl ?? 0, txHash: t.tx_hash || null }));
}

export async function getPositionValue(tradeId) {
  const res = await authFetch(`${BASE}/api/trade/value/${tradeId}`);
  if (!res.ok) throw new Error(`Position value failed: ${res.status}`);
  return await res.json();
}

export async function sellTrade(tradeId) {
  const res = await authFetch(`${BASE}/api/trade/sell/${tradeId}`, { method: 'POST', headers: { 'Content-Type': 'application/json' } });
  if (!res.ok) { let d = ''; try { d = (await res.json()).detail || ''; } catch {} throw new Error(`Sell failed (${res.status}): ${d}`); }
  return await res.json();
}

// ─── LEADERBOARD ─────────────────────────────────────────────────────────────

export async function getLeaderboard(limit = 50, mode = 'paper') {
  const res = await authFetch(`${BASE}/api/leaderboard?limit=${limit}&mode=${mode}`);
  if (!res.ok) throw new Error(`Leaderboard failed: ${res.status}`);
  return (await res.json()).leaderboard || [];
}

export async function getMyRank(walletAddress, mode = 'paper') {
  if (!walletAddress) return null;
  const res = await authFetch(`${BASE}/api/leaderboard/me?wallet_address=${encodeURIComponent(walletAddress.toLowerCase())}&mode=${mode}`);
  if (res.status === 404 || !res.ok) return null;
  return await res.json();
}

// ─── USER STATS & ACHIEVEMENTS ───────────────────────────────────────────────

export async function getUserStats() {
  const wallet = getStoredWallet();
  if (!wallet) return { xp: 0, level: 1, rank: null, streak: 0, xpToNextLevel: 500, xpProgress: 0, totalTrades: 0, winRate: 0 };
  const res = await authFetch(`${BASE}/api/user/stats?wallet_address=${encodeURIComponent(wallet)}`);
  if (!res.ok) throw new Error(`User stats failed: ${res.status}`);
  return await res.json();
}

export async function getAchievements() {
  const wallet = getStoredWallet();
  if (!wallet) return [];
  const res = await authFetch(`${BASE}/api/user/achievements?wallet_address=${encodeURIComponent(wallet)}`);
  if (!res.ok) throw new Error(`Achievements failed: ${res.status}`);
  return (await res.json()).achievements || [];
}

// ─── BRIDGE ──────────────────────────────────────────────────────────────────

export async function getBridgeQuote(amountUsdc) {
  const wallet = getStoredWallet();
  if (!wallet) throw new Error('No wallet connected');
  const res = await authFetch(`${BASE}/api/bridge/quote?wallet_address=${encodeURIComponent(wallet)}&amount_usdc=${amountUsdc}`);
  if (!res.ok) throw new Error(`Bridge quote failed: ${res.status}`);
  return await res.json();
}

export async function startBridge(amountUsdc, lifiTxHash) {
  const wallet = getStoredWallet();
  if (!wallet) throw new Error('No wallet connected');
  const res = await authFetch(`${BASE}/api/bridge/start`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ wallet_address: wallet, amount_usdc: amountUsdc, lifi_tx_hash: lifiTxHash }) });
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
  const res = await authFetch(`${BASE}/api/bridge/history?wallet_address=${encodeURIComponent(wallet)}`);
  if (!res.ok) return { total: 0, bridges: [] };
  return await res.json();
}

// ─── PRETIUM ─────────────────────────────────────────────────────────────────

export async function getPretiumRate(currency = 'KES') {
  const res = await authFetch(`${BASE}/api/pretium/rate?currency=${currency}`);
  if (!res.ok) { const e = await res.json().catch(() => ({})); throw new Error(e.detail || `Rate failed: ${res.status}`); }
  return await res.json();
}

export async function createOnramp({ amount, phoneNumber, walletAddress, mobileNetwork = 'Safaricom', chain = 'BASE', asset = 'USDC', fee = 0, telegramUserId = null }) {
  const res = await authFetch(`${BASE}/api/pretium/onramp`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ amount: Math.round(amount), phone_number: phoneNumber, wallet_address: walletAddress, mobile_network: mobileNetwork, chain, asset, fee, telegram_user_id: telegramUserId }) });
  if (!res.ok) { const e = await res.json().catch(() => ({})); throw new Error(e.detail || `On-ramp failed: ${res.status}`); }
  return await res.json();
}

export async function createOfframp({ amountCrypto, phoneNumber, walletAddress, transactionHash, mobileNetwork = 'Safaricom', chain = 'BASE', asset = 'USDC', fee = 0, telegramUserId = null }) {
  const res = await authFetch(`${BASE}/api/pretium/offramp`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ amount_crypto: amountCrypto, phone_number: phoneNumber, wallet_address: walletAddress, transaction_hash: transactionHash, mobile_network: mobileNetwork, chain, asset, fee, telegram_user_id: telegramUserId }) });
  if (!res.ok) { const e = await res.json().catch(() => ({})); throw new Error(e.detail || `Off-ramp failed: ${res.status}`); }
  return await res.json();
}

export async function getPretiumTransaction(transactionId) {
  const res = await authFetch(`${BASE}/api/pretium/transaction/${transactionId}`);
  if (!res.ok) { const e = await res.json().catch(() => ({})); throw new Error(e.detail || `Transaction failed: ${res.status}`); }
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
  if (!res.ok) { const e = await res.json().catch(() => ({})); throw new Error(e.detail || `Settlement address failed: ${res.status}`); }
  return await res.json();
}

// ─── x402 ────────────────────────────────────────────────────────────────────

export async function verifyPayment(proof, marketId) {
  const wallet = getStoredWallet();
  if (!proof || proof.length < 4) return { valid: false, error: 'Invalid proof' };
  if (!marketId) return { valid: false, error: 'Missing market id' };
  if (!wallet)   return { valid: false, error: 'No wallet connected' };
  const res = await authFetch(`${BASE}/x402/verify`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ proof, wallet_address: wallet, market_id: String(marketId) }) });
  const data = await res.json();
  if (!res.ok || !data.verified) return { valid: false, error: data.reason || data.detail || 'Verification failed' };
  return { valid: true, receipt: data.tx_hash || proof, details: data };
}
