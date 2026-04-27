export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const BACKEND_BASE = (process.env.TELEGRAM_BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/$/, '');
const BOT_TOKEN = process.env.BOT_TOKEN || '';
const BOT_USERNAME = (process.env.TELEGRAM_BOT_USERNAME || 'Nort67Bot').replace(/^@/, '');
const WEBHOOK_SECRET = process.env.TELEGRAM_WEBHOOK_SECRET || '';
const DEFAULT_AUTO_TRADE_AMOUNT = 50.0;

export async function GET() {
  return Response.json({
    ok: true,
    webhook: 'telegram',
    backend: BACKEND_BASE,
    botConfigured: Boolean(BOT_TOKEN),
  });
}

export async function POST(request) {
  if (!BOT_TOKEN) {
    return Response.json({ ok: false, error: 'BOT_TOKEN is not configured' }, { status: 500 });
  }

  if (WEBHOOK_SECRET) {
    const headerSecret = request.headers.get('x-telegram-bot-api-secret-token');
    if (headerSecret !== WEBHOOK_SECRET) {
      return Response.json({ ok: false, error: 'Invalid webhook secret' }, { status: 401 });
    }
  }

  let update;
  try {
    update = await request.json();
  } catch {
    return Response.json({ ok: false, error: 'Invalid JSON payload' }, { status: 400 });
  }

  try {
    await handleUpdate(update);
    return Response.json({ ok: true });
  } catch (error) {
    console.error('[telegram-webhook] unhandled error', error);
    return Response.json({ ok: true, warning: 'update processing failed' });
  }
}

async function handleUpdate(update) {
  if (update?.message?.text) {
    await handleIncomingMessage(update.message);
    return;
  }

  if (update?.callback_query) {
    await handleCallback(update.callback_query);
  }
}

async function handleIncomingMessage(message) {
  const chatId = message.chat?.id;
  if (!chatId) return;

  const text = (message.text || '').trim();
  if (!text) return;

  const username = message.from?.username || null;
  await syncTelegramState(chatId, username);

  const commandParts = text.split(/\s+/);
  const command = normalizeCommand(commandParts[0]);
  const lang = await getPreferredLanguage(chatId);

  switch (command) {
    case '/start':
      await sendMenu(chatId);
      return;
    case '/lang':
    case '/language':
      await handleLanguageCommand(chatId, commandParts);
      return;
    case '/enable_autotrade':
      await handleAutoTradeToggle(chatId, true);
      return;
    case '/disable_autotrade':
      await handleAutoTradeToggle(chatId, false);
      return;
    case '/set_limit':
      await handleSetLimit(chatId, commandParts);
      return;
    case '/trending':
      await handleTrending(chatId);
      return;
    case '/advice':
    case '/premium_advice':
      await handleAdvice(chatId, commandParts, lang);
      return;
    case '/pay':
      await handlePaymentProof(chatId, commandParts, lang);
      return;
    case '/portfolio':
      await handlePortfolio(chatId);
      return;
    case '/markets':
      await handleMarkets(chatId);
      return;
    case '/signals':
      await handleSignals(chatId);
      return;
    case '/papertrade':
      await handlePaperTrade(chatId, commandParts);
      return;
    default:
      await sendDefaultHelp(chatId);
  }
}

async function handleCallback(callbackQuery) {
  const chatId = callbackQuery.message?.chat?.id;
  if (!chatId) return;

  await answerCallbackQuery(callbackQuery.id);

  const callData = callbackQuery.data || '';
  const username = callbackQuery.from?.username || null;
  await syncTelegramState(chatId, username);

  if (callData.startsWith('lang_')) {
    const newLang = callData.slice(5);
    await setLanguage(chatId, newLang);
    await sendText(chatId, `Language updated to: ${newLang === 'sw' ? 'Kiswahili' : 'English'}`);
    return;
  }

  if (callData.startsWith('exe_yes_')) {
    await handleExecuteCallback(chatId, callData);
    return;
  }

  if (callData === 'exe_no') {
    await sendText(chatId, 'Trade auto-execution cancelled.');
    return;
  }

  switch (callData) {
    case 'btn_trending':
      await handleTrending(chatId);
      return;
    case 'btn_advice':
      await sendText(chatId, 'Usage: /advice <market_id>\nExample: /advice 527079\n\nIf premium advice is locked, pay and then send /pay <tx_hash>.');
      return;
    case 'btn_portfolio':
      await handlePortfolio(chatId);
      return;
    default:
      await sendText(chatId, 'Unknown action.');
  }
}

function normalizeCommand(command) {
  const lower = (command || '').toLowerCase();
  const botSuffix = `@${BOT_USERNAME.toLowerCase()}`;
  return lower.endsWith(botSuffix) ? lower.slice(0, -botSuffix.length) : lower;
}

async function handleLanguageCommand(chatId, commandParts) {
  if (commandParts.length < 2) {
    await sendLanguageMenu(chatId);
    return;
  }

  const newLang = commandParts[1].toLowerCase();
  if (newLang !== 'en' && newLang !== 'sw') {
    await sendText(chatId, "Unsupported language. Use '/lang en' or '/lang sw'.");
    return;
  }

  await setLanguage(chatId, newLang);
  await sendText(chatId, `Language updated to: ${newLang === 'sw' ? 'Kiswahili' : 'English'}`);
}

async function handleAutoTradeToggle(chatId, enabled) {
  await sendText(chatId, `${enabled ? 'Enabling' : 'Disabling'} auto-trade permissions...`);
  const result = await apiPost('/api/permissions', {
    telegram_user_id: String(chatId),
    auto_trade: enabled,
    limit: null,
  });
  await sendText(chatId, formatJsonOrRaw('Permission update', result.text));
}

async function handleSetLimit(chatId, commandParts) {
  if (commandParts.length < 2) {
    await sendText(chatId, 'Usage: /set_limit <amount>\nExample: /set_limit 100');
    return;
  }

  const limit = Number(commandParts[1]);
  if (!Number.isFinite(limit) || limit <= 0) {
    await sendText(chatId, 'Invalid amount. Please use numbers only.');
    return;
  }

  await sendText(chatId, `Setting auto-trade limit to $${limit.toFixed(2)}...`);
  const result = await apiPost('/api/permissions', {
    telegram_user_id: String(chatId),
    auto_trade: null,
    limit,
  });
  await sendText(chatId, formatJsonOrRaw('Limit update', result.text));
}

async function handleTrending(chatId) {
  await sendText(chatId, 'Fetching top trending markets...');
  const result = await apiGet('/api/markets/?limit=10&sort_by=volume&category=crypto');
  if (!result.ok) {
    await sendText(chatId, 'Unable to retrieve trending markets at this time.');
    return;
  }

  try {
    const json = JSON.parse(result.text);
    const markets = Array.isArray(json) ? json : (json.markets || []);
    if (!markets.length) {
      await sendText(chatId, 'No trending markets are available right now.');
      return;
    }

    const lines = ['TOP TRENDING MARKETS', '--------------------------------', ''];
    for (let i = 0; i < markets.length; i += 1) {
      const market = markets[i];
      const odds = Number(market.current_odds || 0);
      const expires = String(market.expires_at || '?').split(' ')[0];
      lines.push(`${i + 1}. ${market.question || 'Unknown'}`);
      lines.push(`   ID: ${market.id || '?'}`);
      lines.push(`   Volume: $${formatNumber(market.volume || 0)} | Odds: ${odds > 0 ? `${Math.round(odds * 100)}%` : '-'} | Expires: ${expires}`);
      lines.push('');
    }
    lines.push('Use /advice <id> for premium analysis.');
    await sendText(chatId, lines.join('\n'));
  } catch {
    await sendText(chatId, 'Unable to retrieve trending markets at this time.');
  }
}

async function handleAdvice(chatId, commandParts, lang) {
  if (commandParts.length < 2) {
    await sendText(chatId, 'Usage: /advice <market_id>\nExample: /advice 527079');
    return;
  }

  const marketId = commandParts[1];
  await setPendingPremiumMarket(chatId, marketId);
  await sendText(chatId, `Analyzing market ${marketId} (${lang === 'sw' ? 'Kiswahili' : 'English'})...`);

  const result = await apiPost('/api/agent/advice', {
    market_id: String(marketId),
    telegram_id: String(chatId),
    premium: true,
    language: lang,
  });

  if (isBackendUnavailable(result.text)) {
    await sendText(chatId, 'The backend is currently waking up or unavailable. Please wait 30 seconds and try again.');
    return;
  }

  if (result.status === 402 || looksLikePaymentRequired(result.text)) {
    await sendPaymentInstructions(chatId, marketId, result.text);
    return;
  }

  await sendPremiumAdvice(chatId, marketId, result.text);
}

async function handlePaymentProof(chatId, commandParts, lang) {
  if (commandParts.length < 2) {
    await sendText(chatId, 'Usage: /pay <tx_hash>\nExample: /pay 0xabc123...');
    return;
  }

  const txHash = commandParts[1];
  if (!/^0x[0-9a-fA-F]{64}$/.test(txHash)) {
    await sendText(chatId, 'Invalid transaction hash. It should look like /pay 0xabc123...');
    return;
  }

  const profile = await getTelegramProfile(chatId);
  const marketId = profile?.pending_premium_market_id;
  if (!marketId) {
    await sendText(chatId, 'I do not have a pending premium request for you. Run /advice <market_id> first.');
    return;
  }

  await sendText(chatId, `Verifying payment on Base for market ${marketId}...`);
  const verifyResult = await apiPost('/api/x402/verify', {
    proof: txHash,
    telegram_id: String(chatId),
    market_id: String(marketId),
  });

  try {
    const verifyJson = JSON.parse(verifyResult.text);
    if (verifyJson.success || verifyJson.verified) {
      await sendText(chatId, 'Payment verified. Unlocking premium advice...');
      const unlocked = await apiPost('/api/agent/advice', {
        market_id: String(marketId),
        telegram_id: String(chatId),
        premium: true,
        language: lang,
      });

      if (looksLikePaymentRequired(unlocked.text)) {
        await sendText(chatId, `Payment verification succeeded, but premium advice is still locked. Please try /advice ${marketId} again.`);
        return;
      }

      await sendPremiumAdvice(chatId, marketId, unlocked.text);
      await setPendingPremiumMarket(chatId, null);
      return;
    }

    await sendText(chatId, `Payment not verified. Details: ${verifyJson.reason || 'Unknown error'}`);
  } catch (error) {
    await sendText(chatId, `Verification error: ${error.message}\nRaw: ${preview(verifyResult.text)}`);
  }
}

async function handlePortfolio(chatId) {
  const result = await apiGet(`/api/wallet/summary?telegram_user_id=${encodeURIComponent(String(chatId))}`);
  if (!result.ok || !result.text || result.text.startsWith('Connection failed')) {
    await sendText(chatId, 'Portfolio summary is unavailable right now.');
    return;
  }

  await sendText(chatId, `PORTFOLIO SUMMARY\n--------------------------------\n${result.text}`);
}

async function handleMarkets(chatId) {
  await sendText(chatId, 'Fetching market data...');
  const result = await apiGet('/api/markets/?limit=50');
  let output = result.text;
  if (result.ok) {
    try {
      const json = JSON.parse(result.text);
      output = formatMarkets(json.markets || []);
    } catch {
      output = result.text;
    }
  }

  await sendText(chatId, `LIVE MARKETS\n--------------------------------\n\n${output || 'No market data available at this time.'}`);
}

async function handleSignals(chatId) {
  await sendText(chatId, 'Analyzing market momentum...');
  const result = await apiGet('/api/signals/?top=10');
  if (!result.ok) {
    await sendText(chatId, 'Signals are unavailable right now.');
    return;
  }

  try {
    const payload = JSON.parse(result.text);
    const signalList = Array.isArray(payload) ? payload : payload[Object.keys(payload)[0]] || [];
    const lines = ['TOP MARKET SIGNALS', '--------------------------------', ''];

    for (let i = 0; i < signalList.length; i += 1) {
      const signal = signalList[i];
      const score = Math.round(Number(signal.score || 0) * 100);
      const odds = Number(signal.current_odds || 0);
      lines.push(`${i + 1}. ${signal.question || 'Unknown'}`);
      lines.push(`   ID: ${signal.market_id || '?'} | Score: ${score}%`);
      lines.push(`   Volume: $${formatNumber(signal.volume || 0)} | Odds: ${odds > 0 ? `${Math.round(odds * 100)}%` : '-'}`);
      lines.push(`   Note: ${signal.reason || ''}`);
      lines.push('');
    }

    lines.push('Use /advice <id> to get a full AI analysis.');
    await sendText(chatId, lines.join('\n'));
  } catch (error) {
    await sendText(chatId, `Signal parse error: ${error.message}\nRaw preview: ${preview(result.text)}`);
  }
}

async function handlePaperTrade(chatId, commandParts) {
  if (commandParts.length < 4) {
    await sendText(chatId, 'Usage: /papertrade <market_id> <yes/no> <amount>\nExample: /papertrade 527079 yes 50');
    return;
  }

  const amount = Number(commandParts[3]);
  if (!Number.isFinite(amount) || amount <= 0) {
    await sendText(chatId, 'Invalid amount. Please use numbers only (e.g. 50, 100.50).');
    return;
  }

  const marketId = commandParts[1];
  const side = String(commandParts[2] || '').toUpperCase() === 'NO' ? 'NO' : 'YES';
  const marketQuestion = await resolveMarketQuestion(marketId);
  const pricePerShare = 0.5;
  const shares = amount / pricePerShare;

  const result = await apiPost('/api/papertrade', {
    telegram_user_id: String(chatId),
    market_id: String(marketId),
    market_question: marketQuestion,
    outcome: side,
    shares,
    price_per_share: pricePerShare,
    direction: 'BUY',
  });

  await sendText(chatId, `PAPER TRADE RESULT\n--------------------------------\n${result.text}`);
}

async function handleExecuteCallback(chatId, callData) {
  const parts = callData.split('_');
  if (parts.length < 4) {
    await sendText(chatId, 'Unable to parse trade execution request.');
    return;
  }

  const permissions = await getTelegramPermissions(chatId);
  if (!permissions.auto_trade) {
    await sendText(chatId, 'Auto-trade is disabled. Enable it first with /enable_autotrade.');
    return;
  }

  const marketId = parts[2];
  const side = parts[3];
  const limit = Number(permissions.limit ?? DEFAULT_AUTO_TRADE_AMOUNT);
  const amount = Math.min(DEFAULT_AUTO_TRADE_AMOUNT, limit);

  if (!(amount > 0)) {
    await sendText(chatId, 'Your auto-trade limit must be greater than 0. Use /set_limit <amount> first.');
    return;
  }

  await sendText(chatId, `Executing trade... Placing $${amount.toFixed(2)} on ${side} for market ${marketId}`);
  const marketQuestion = await resolveMarketQuestion(marketId);
  const result = await apiPost('/api/papertrade', {
    telegram_user_id: String(chatId),
    market_id: String(marketId),
    market_question: marketQuestion,
    outcome: String(side).toUpperCase() === 'NO' ? 'NO' : 'YES',
    shares: amount / 0.5,
    price_per_share: 0.5,
    direction: 'BUY',
  });
  await sendText(chatId, `Trade Result:\n${result.text}`);
}

async function syncTelegramState(chatId, username) {
  await apiPost('/api/telegram/user/upsert', {
    telegram_id: String(chatId),
    username: username || null,
    language: null,
  });
}

async function getPreferredLanguage(chatId) {
  const profile = await getTelegramProfile(chatId);
  return profile?.language || 'en';
}

async function getTelegramProfile(chatId) {
  const result = await apiGet(`/api/telegram/user/${encodeURIComponent(String(chatId))}`);
  if (!result.ok) return null;
  try {
    return JSON.parse(result.text);
  } catch {
    return null;
  }
}

async function getTelegramPermissions(chatId) {
  const result = await apiGet(`/api/telegram/permissions/${encodeURIComponent(String(chatId))}`);
  if (!result.ok) {
    return { auto_trade: false, limit: DEFAULT_AUTO_TRADE_AMOUNT };
  }

  try {
    return JSON.parse(result.text);
  } catch {
    return { auto_trade: false, limit: DEFAULT_AUTO_TRADE_AMOUNT };
  }
}

async function setLanguage(chatId, language) {
  await apiPost('/api/telegram/preferences/language', {
    telegram_id: String(chatId),
    language,
  });
}

async function setPendingPremiumMarket(chatId, marketId) {
  await apiPost('/api/telegram/session/premium-request', {
    telegram_id: String(chatId),
    market_id: marketId,
  });
}

async function resolveMarketQuestion(marketId) {
  const result = await apiGet(`/api/markets/${encodeURIComponent(String(marketId))}`);
  if (!result.ok) return `Market ${marketId}`;
  try {
    const market = JSON.parse(result.text);
    return market.question || `Market ${marketId}`;
  } catch {
    return `Market ${marketId}`;
  }
}

async function sendPaymentInstructions(chatId, marketId, premiumResponse) {
  try {
    const paymentJson = JSON.parse(premiumResponse);
    const amount = Number(paymentJson.amount || 0.1);
    const address = paymentJson.address || 'NORT_TREASURY_ADDRESS';
    const asset = paymentJson.asset || 'USDC';
    const chain = paymentJson.chain || 'Base';
    await sendText(
      chatId,
      `Premium advice for market ${marketId} is locked.\n\nSend $${amount.toFixed(2)} ${asset} on ${chain} to:\n${address}\n\nThen send proof with:\n/pay <tx_hash>`
    );
  } catch {
    await sendText(
      chatId,
      `Premium advice for market ${marketId} is locked.\n\nComplete the x402 payment, then send proof with:\n/pay <tx_hash>\n\nRaw payment response: ${preview(premiumResponse)}`
    );
  }
}

async function sendPremiumAdvice(chatId, marketId, premiumResponse) {
  try {
    const json = JSON.parse(premiumResponse);
    if (!json.summary) {
      await sendText(chatId, `Premium content for market ${marketId}:\n\n${json.content || preview(premiumResponse)}`);
      return;
    }

    const summary = json.summary || '';
    const why = json.why_trending || '';
    const plan = json.suggested_plan || 'WAIT';
    const disclaimer = json.disclaimer || 'This is not financial advice.';
    const confidence = Number(json.confidence || 0.5);
    const staleWarn = json.stale_data_warning || '';
    const riskList = formatRiskFactors(json.risk_factors);

    const message = [
      `MARKET ANALYSIS: ${json.market_id || marketId}`,
      '',
      'SUMMARY',
      summary,
      '',
      'TREND ANALYSIS',
      why,
      '',
      'RISK FACTORS',
      riskList,
      '',
      `RECOMMENDED ACTION: ${plan}`,
      `CONFIDENCE: ${Math.round(confidence * 100)}%`,
      staleWarn ? `\nDATA WARNING: ${staleWarn}` : '',
      '',
      disclaimer,
    ].filter(Boolean).join('\n');

    if (!String(plan).toUpperCase().includes('WAIT')) {
      const side = deriveTradeSide(plan);
      await sendAdviceWithExecuteOption(chatId, message, marketId, side);
      return;
    }

    await sendText(chatId, message);
  } catch {
    await sendText(chatId, `Unable to parse premium advice.\nRaw preview: ${preview(premiumResponse)}`);
  }
}

function formatRiskFactors(risks) {
  if (!Array.isArray(risks) || !risks.length) return 'None listed';
  return risks.map((risk) => `- ${risk}`).join('\n');
}

function deriveTradeSide(plan) {
  const normalizedPlan = String(plan).toUpperCase();
  if (normalizedPlan.includes('NO') || normalizedPlan.includes('SELL')) return 'NO';
  return 'YES';
}

function isBackendUnavailable(response) {
  return response.includes('503') || response.startsWith('Connection failed') || response.startsWith('Error 5');
}

function looksLikePaymentRequired(response) {
  return response.includes('"amount"')
    || response.includes('PAYMENT-REQUIRED')
    || response.includes('payment required')
    || response.includes('"address"')
    || response.includes('"asset"');
}

function formatJsonOrRaw(title, payload) {
  try {
    return `${title}:\n${JSON.stringify(JSON.parse(payload), null, 2)}`;
  } catch {
    return `${title}:\n${payload}`;
  }
}

function preview(text) {
  if (!text) return '';
  return text.slice(0, 300);
}

function formatMarkets(markets) {
  if (!Array.isArray(markets) || !markets.length) return 'No market data available at this time.';
  return markets.slice(0, 20).map((market, index) => {
    const odds = Number(market.current_odds || 0);
    return `${index + 1}. ${market.question || 'Unknown'}\nID: ${market.id || '?'} | Odds: ${odds > 0 ? `${Math.round(odds * 100)}%` : '-'} | Volume: $${formatNumber(market.volume || 0)}`;
  }).join('\n\n');
}

function formatNumber(value) {
  return Number(value || 0).toLocaleString('en-US', { maximumFractionDigits: 0 });
}

async function sendMenu(chatId) {
  await sendTelegram('sendMessage', {
    chat_id: chatId,
    text:
      'NORT67 AI MARKET ANALYST\n\n' +
      'Real-time prediction market analysis powered by live market data, AI reasoning, and Telegram bot workflows.\n\n' +
      'Core commands: /advice /signals /trending /portfolio /lang\n' +
      'Payment flow: /advice <market_id> then /pay <tx_hash>',
    reply_markup: {
      inline_keyboard: [
        [
          { text: 'Trending Markets', callback_data: 'btn_trending' },
          { text: 'AI Advice', callback_data: 'btn_advice' },
        ],
        [
          { text: 'Portfolio', callback_data: 'btn_portfolio' },
        ],
        [
          { text: 'Set Language', callback_data: 'lang_sw' },
        ],
      ],
    },
  });
}

async function sendLanguageMenu(chatId) {
  await sendTelegram('sendMessage', {
    chat_id: chatId,
    text: 'Select your preferred language / Chagua lugha unayopendelea:',
    reply_markup: {
      inline_keyboard: [
        [
          { text: 'English', callback_data: 'lang_en' },
          { text: 'Kiswahili', callback_data: 'lang_sw' },
        ],
      ],
    },
  });
}

async function sendAdviceWithExecuteOption(chatId, text, marketId, side) {
  await sendTelegram('sendMessage', {
    chat_id: chatId,
    text: trimTelegramText(`${text}\n\nAuto-execute this trade?`),
    reply_markup: {
      inline_keyboard: [
        [
          { text: 'Yes', callback_data: `exe_yes_${marketId}_${side}` },
          { text: 'No', callback_data: 'exe_no' },
        ],
      ],
    },
  });
}

async function sendText(chatId, text) {
  await sendTelegram('sendMessage', {
    chat_id: chatId,
    text: trimTelegramText(text),
  });
}

async function answerCallbackQuery(callbackQueryId) {
  if (!callbackQueryId) return;
  await sendTelegram('answerCallbackQuery', { callback_query_id: callbackQueryId });
}

function trimTelegramText(text) {
  const value = String(text || '');
  if (value.length <= 4096) return value;
  return `${value.slice(0, 4090)}\n[...]`;
}

async function sendTelegram(method, payload) {
  const response = await fetch(`https://api.telegram.org/bot${BOT_TOKEN}/${method}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const body = await response.text();
    console.error(`[telegram-webhook] Telegram API error on ${method}`, response.status, body);
  }
}

async function apiGet(path) {
  try {
    const response = await fetch(`${BACKEND_BASE}${path}`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
      cache: 'no-store',
    });
    const text = await response.text();
    return { ok: response.ok, status: response.status, text };
  } catch {
    return { ok: false, status: 503, text: 'Connection failed.' };
  }
}

async function apiPost(path, body) {
  try {
    const response = await fetch(`${BACKEND_BASE}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      cache: 'no-store',
    });
    const text = await response.text();
    return { ok: response.ok, status: response.status, text };
  } catch {
    return { ok: false, status: 503, text: 'Connection failed.' };
  }
}

async function sendDefaultHelp(chatId) {
  await sendText(
    chatId,
    'NORT67 AI MARKET ANALYST\n\n' +
      'Available commands:\n' +
      '/trending - Hottest markets by volume\n' +
      '/advice <id> - Premium AI analysis for a market\n' +
      '/premium_advice <id> - Alias for /advice\n' +
      '/pay <tx_hash> - Submit x402 payment proof\n' +
      '/signals - Algorithmic trading signals\n' +
      '/markets - Live market listings\n' +
      '/portfolio - Wallet or paper summary\n' +
      '/papertrade <id> yes/no <amount> - Simulate trades\n' +
      '/lang - Set your preferred language (en/sw)\n\n' +
      'Settings:\n' +
      '/enable_autotrade - Enable automated execution\n' +
      '/disable_autotrade - Disable automated execution\n' +
      '/set_limit <amount> - Set auto-trade limit\n\n' +
      'Type /start for the interactive menu.'
  );
}
