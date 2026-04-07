# Polymarket AI Assistant — Complete Flow & Story

> A full walkthrough of what we built, why every piece exists, and how it all works together.

---

## The Story — Why This Exists

Polymarket is a prediction market platform. People bet on real-world outcomes — "Will BTC hit $100k?", "Will the Fed cut rates?", "Who wins the next election?" — using real money. The market price reflects the crowd's collective probability estimate.

The problem is scale. At any given moment there are **hundreds of active markets**. A user who wants to find an opportunity has to manually browse through all of them, figure out which ones are moving, which ones have activity, and whether any of them are worth trading.

That's exactly what we automated.

**We built an AI-powered assistant that:**
- Watches all the markets for you
- Surfaces the most interesting ones automatically
- Explains in plain English why each one ranked
- Lets an AI agent give you structured trading advice
- Gates premium advice behind a micro-payment
- Logs all your paper trades safely
- Shows everything on a live dashboard

All in paper trading mode — no real money, no real risk, fully demonstrable by Friday.

---

## The Cast — Who Built What

| Person | Role | What They Own |
|---|---|---|
| Intern 1 | Market Data | Fetches Polymarket markets, stores them in SQLite |
| Intern 2 | Signals Engine (Quant) | Scores and ranks markets, powers GET /signals |
| Intern 3 | NORT Bot Agent | AI advice layer using OpenRouter |
| Intern 4 | Telegram Bot + x402 | All bot commands, payment gating |
| Intern 5 | Paper Trading | Paper trade engine and wallet |
| Intern 6 | Dashboard | Next.js web UI showing all live data |

---

## The Architecture — Three Layers

```
┌─────────────────────────────────────────────┐
│              USER INTERFACES                │
│   Telegram Bot          Next.js Dashboard   │
│   (remote control)      (command center)    │
└──────────────┬───────────────────┬──────────┘
               │                   │
               ▼                   ▼
┌─────────────────────────────────────────────┐
│              FASTAPI BACKEND                │
│  Markets API  │  Signals API  │  Trades API │
│  x402 Verify  │  Agent Route  │  Wallet API │
└──────────────┬───────────────────┬──────────┘
               │                   │
               ▼                   ▼
┌─────────────────────────────────────────────┐
│            DATA & INTELLIGENCE              │
│   SQLite Database      NORT Bot + OpenRouter│
│   (assistant.db)       (AI advice only)     │
└─────────────────────────────────────────────┘
```

Everything flows through the FastAPI backend. The user interfaces never talk to the database or the AI directly — the backend is the single source of truth.

---

## The Database — Five Tables

File location: `data/assistant.db`

```
┌─────────────────┐   ┌──────────────────┐   ┌─────────────────┐
│     Market      │   │    AISignal      │   │      Trade      │
│─────────────────│   │──────────────────│   │─────────────────│
│ id              │◄──│ market_id        │   │ id              │
│ question        │   │ prediction       │   │ user_id         │
│ category        │   │ confidence_score │   │ market_id       │
│ current_odds    │   │ analysis_summary │   │ outcome_selected│
│ is_active       │   │ timestamp        │   │ bet_amount      │
│ expires_at      │   └──────────────────┘   │ odds_at_time    │
└─────────────────┘                          │ status          │
                                             └─────────────────┘
┌─────────────────┐   ┌──────────────────┐
│      User       │   │    Payment       │
│─────────────────│   │──────────────────│
│ id              │◄──│ user_id          │
│ wallet_address  │   │ market_id        │
│ telegram_id     │   │ amount           │
│ username        │   │ tx_hash          │
│ created_at      │   │ is_confirmed     │
└─────────────────┘   └──────────────────┘
```

- **Market** — populated by Intern 1 from the Polymarket API
- **AISignal** — populated by Intern 2's signals engine after every `/signals` call
- **Trade** — populated by Intern 5's paper trading engine
- **User** — created when someone first uses the bot
- **Payment** — populated by Intern 4's x402 verification flow

---

## The Two Command Paths

Every request in the system takes one of two paths. This is the most important architectural decision.

### Path 1 — Fast Path (No AI)

```
User → Telegram Bot → FastAPI Backend → SQLite → Response
```

Used for all normal commands. Fast, cheap, no AI involved.

```
/trending       → top markets by volume right now
/market <id>    → single market detail
/signals        → ranked opportunities with reasons  ← Intern 2's work
/portfolio      → paper wallet summary
/papertrade     → log a paper trade
```

### Path 2 — Agent Path (With AI)

```
User → Telegram Bot → (x402 check) → FastAPI → NORT Bot → OpenRouter → LLM → Response
```

Used only when the user explicitly asks for advice. Slower, costs tokens, produces structured analysis.

```
/advice <id>           → free AI analysis
/premium_advice <id>   → locked until payment proof submitted
/pay <proof>           → submits x402 proof to unlock premium
```

**The rule is absolute: NORT Bot runs ONLY for advice commands. Never for anything else.**

---

## The Complete Journey — Step by Step

### What happens when a user types `/signals`

```
1. User types /signals in Telegram

2. Telegram bot (apps/telegram-bot/commands.py)
   → calls GET /signals?top=20 on the FastAPI backend

3. FastAPI signals route (services/backend/api/signals.py)
   → opens a SQLite session
   → runs: SELECT * FROM market WHERE is_active = true
   → gets back all active markets Intern 1 stored

4. Signals engine (services/backend/core/signals_engine.py)
   → receives the full market list
   → STEP 1: liquidity filter — drops markets below $1,000 volume
   → STEP 2: scores each remaining market
        momentum_score()     = abs(current_odds - previous_odds) / previous_odds
        volume_spike_score() = current_volume / avg_volume (capped at 5x)
        composite_score()    = (0.5 × momentum) + (0.5 × volume)
   → STEP 3: sorts by composite score, highest first
   → STEP 4: builds a reason string for each
        "Price moved +44.0% with 16.0x average volume."
   → returns top 20

5. signals.py saves a snapshot to the AISignal table
   → Intern 6 reads this for the Dashboard Signals page
   → Intern 3's NORT Bot reads this when generating advice

6. Response returned to Telegram as JSON

7. Telegram bot formats and sends to user:

   📊 Top Signals

   #1 Will BTC hit $100k by March?
   Score: 0.72 | Odds: 72%
   Price moved +44.0% with 16.0x average volume.

   #2 Will Fed cut rates in Q1?
   Score: 0.61 | Odds: 65%
   Price moved +62.5% with 3.0x average volume.
   ...
```

---

### What happens when a user types `/advice market-001`

```
1. User types /advice market-001 in Telegram

2. Telegram bot calls POST /agent/advice on the backend
   with { market_id: "market-001" }

3. FastAPI backend receives the request
   → this is an advice command → routes to NORT Bot
   → no x402 check needed (free advice)

4. NORT Bot agent (services/agent/) activates
   → calls get_market("market-001")    → fetches market from backend
   → calls get_signals()               → fetches current signal snapshot
   → calls get_wallet_summary()        → fetches user's paper trade history

5. NORT Bot builds a structured prompt using prompt_templates.py
   → sends it to OpenRouter API
   → OpenRouter routes to the configured LLM (e.g. Claude, GPT-4o)

6. LLM returns structured advice

7. NORT Bot formats it into the required output:

   📋 MARKET ANALYSIS — Will BTC hit $100k by March?

   SUMMARY
   This market has seen significant momentum over the past 6 hours,
   with odds jumping from 50% to 72% on unusually high volume...

   WHY TRENDING
   Large volume spike suggests informed traders are positioning...

   RISK FACTORS
   - Market expires in 3 weeks — time decay risk
   - BTC historically volatile around macro events
   - Current odds may already price in the move

   SUGGESTED PLAN
   Consider a small Yes position given momentum, but size conservatively...

   ⚠️ DISCLAIMER
   This is not financial advice. Paper mode only. No real funds at risk.

8. Response sent back to Telegram user
```

---

### What happens when a user types `/premium_advice market-001`

```
1. User types /premium_advice market-001 in Telegram

2. Telegram bot checks — has this user paid?
   → No payment proof on file
   → Bot replies: "This is a premium feature. Pay and send proof with /pay <proof>"

3. User gets proof string from the x402 payment flow
   → Types: /pay abc123proofstring

4. Telegram bot calls POST /x402/verify
   with { proof: "abc123proofstring", user_id: "telegram-user-id" }

5. Backend x402 verifier checks the proof
   → Valid format? ✓
   → Amount correct? ✓
   → Not already used? ✓
   → Stores receipt in Payment table
   → Returns: { verified: true }

6. Bot now calls POST /agent/advice (same as free advice)
   but with a premium=true flag, which may unlock deeper analysis

7. NORT Bot runs the full analysis (same flow as /advice above)

8. Premium advice returned to user
```

---

### What happens when a user types `/papertrade`

```
1. User types /papertrade market-001 YES 50 in Telegram
   (meaning: bet $50 on YES for market-001)

2. Telegram bot calls POST /papertrade on the backend
   with { market_id: "market-001", outcome: "YES", amount: 50 }

3. Backend paper trading engine (Intern 5)
   → checks user's paper wallet balance
   → deducts $50 from paper balance
   → stores the trade in the Trade table:
        market_id: market-001
        outcome_selected: YES
        bet_amount: 50
        odds_at_time: 0.72
        status: Open

4. Optional: if EXECUTION_MODE=COMMIT_TX
   → backend submits a receipt to Polygon testnet
   → returns a tx_hash as proof the trade was logged

5. Bot replies: "Paper trade logged! Bet $50 on YES at 72% odds."

6. Dashboard Trades page updates in real time
   → Intern 6 polls the backend → new trade appears
```

---

## The Signals Engine — Deep Dive

This is Intern 2's contribution. It is the intelligence layer between raw market data and useful rankings.

### Why it exists

Without the signals engine, the system can only answer "here are all the markets." With it, the system can answer "here are the markets you should actually pay attention to right now, and here's why."

### The scoring pipeline

```
All Markets (hundreds)
        │
        ▼
┌───────────────────────┐
│   Liquidity Filter    │  ← drops markets with volume < $1,000
│                       │     kills noise before it reaches scoring
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│   Momentum Score      │  ← measures price change
│                       │     (current_odds - previous_odds) / previous_odds
│                       │     normalized 0.0 → 1.0
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│  Volume Spike Score   │  ← measures unusual activity
│                       │     current_volume / avg_volume
│                       │     capped at 5x = score of 1.0
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│   Composite Score     │  ← combines both
│                       │     (0.5 × momentum) + (0.5 × volume)
│                       │     final number between 0.0 and 1.0
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│    Reason String      │  ← plain English explanation
│                       │     "Price moved +44.0% with 16.0x average volume."
└───────────┬───────────┘
            │
            ▼
      Top 20 Ranked
```

### Why each filter/score matters

**Liquidity Filter** — A market with 2 trades and $10 volume could have a 100% price move and score #1 without this filter. That's not a signal, that's noise. The filter ensures only tradeable markets get ranked.

**Momentum** — Price movement is the clearest sign that new information entered the market. When odds jump from 50% to 72%, people who know something are betting. That's worth surfacing.

**Volume Spike** — Price alone can be one big trade. Volume confirms that many participants are reacting, not just one whale. High price move + high volume = genuine market event.

**Composite** — Requiring both signals means a market needs to show real activity across two dimensions to rank high. This reduces false positives.

**Reason String** — A score of 0.72 is meaningless to a human. "Price moved +44% with 16x average volume" is immediately understandable. This is what makes the system feel intelligent rather than just mathematical.

### What the signals engine feeds

```
signals_engine output
        │
        ├──→ Telegram /signals command (Intern 4 reads it)
        ├──→ Dashboard Signals page (Intern 6 reads it)
        ├──→ AISignal table in SQLite (snapshot stored after every call)
        └──→ NORT Bot get_signals() tool (Intern 3's agent reads it for advice)
```

**If the signals engine doesn't work, all four of these break.**

---

## NORT Bot + OpenRouter — The AI Layer

### What OpenRouter is

OpenRouter is a gateway that sits between our code and the actual AI model. Instead of calling OpenAI or Anthropic directly, we call OpenRouter once and it handles routing to whichever model we configured.

```
Our Code (NORT Bot)
        │
        ▼
OpenRouter API (openrouter.ai/api/v1)
        │
        ├──→ anthropic/claude-3-haiku
        ├──→ openai/gpt-4o
        ├──→ mistralai/mistral-7b
        └──→ (any supported model)
```

To swap models, change one line in `agent.json`. No code changes.

### What NORT Bot is

NORT Bot is not a chatbot. It is a structured reasoning agent. It always produces the same output format regardless of which market it analyzes:

```json
{
  "summary": "...",
  "why_trending": "...",
  "risk_factors": ["...", "...", "..."],
  "suggested_plan": "...",
  "disclaimer": "This is not financial advice. Paper mode only."
}
```

It has three tools it can call to gather information before reasoning:

```
get_market(id)         → current odds, volume, expiry, category
get_signals()          → where this market ranks, momentum score, reason
get_wallet_summary()   → user's open positions, paper balance, trade history
```

It reads all three before writing its analysis. It cannot write to anything — read only.

---

## The x402 Payment Layer

x402 is an HTTP-native micro-payment protocol. Instead of a monthly subscription, users pay per premium query.

### The philosophy

- `/signals` — free. Anyone can see ranked markets.
- `/advice` — free. Basic AI analysis is available to all.
- `/premium_advice` — paid. Deeper analysis costs a small amount per query.

This demonstrates the monetization model without requiring a real payment system on day one. For the demo, proof strings are mocked.

### The flow

```
User: /premium_advice market-001
        │
        ▼
Bot: "Premium feature. Use /pay <proof> to unlock."
        │
        ▼
User: /pay abc123proof
        │
        ▼
Bot → POST /x402/verify { proof: "abc123proof" }
        │
        ▼
Backend checks:
  → Valid format?      ✓
  → Correct amount?    ✓
  → Not reused?        ✓
        │
        ▼
Receipt stored in Payment table
        │
        ▼
NORT Bot activated → full premium advice returned
```

---

## The Dashboard — What It Shows

The Next.js dashboard is the visual layer. It polls the FastAPI backend every few seconds and displays live data across 6 pages.

| Page | Data Source | What You See |
|---|---|---|
| Overview | backend health check | Is the server up? Last sync time? |
| Markets | GET /markets | All active markets with current odds |
| Signals | AISignal table | Ranked markets with scores and reasons |
| Wallet | GET /wallet/summary | Paper balance, open positions, P&L |
| Trades | Trade table | Full history of all paper trades |
| Logs | telemetry_logs | Every API request, errors, agent calls |

The dashboard never calls Polymarket directly. All data flows through the backend. This means caching works correctly and there's one source of truth.

---

## The Friday Demo — Full Script

This is the sequence that shows every component working end to end.

```
STEP 1 → /trending
         Shows: top markets load instantly from cache
         Proves: Intern 1's market data pipeline works

STEP 2 → /advice <id>
         Shows: structured AI analysis appears
         Proves: NORT Bot + OpenRouter working, signals feeding the agent

STEP 3 → /premium_advice <id>
         Shows: "locked, payment required" message
         Proves: x402 gating is active, premium is protected

STEP 4 → /pay <proof>
         Shows: payment verified, premium advice unlocks
         Proves: x402 verification flow works end to end

STEP 5 → /papertrade
         Shows: trade logged, wallet balance updates
         Proves: paper trading engine storing data correctly

STEP 6 → Open Dashboard
         Shows: signals page and trades page updated in real time
         Proves: dashboard is reading live backend data, full system visible
```

---

## The Rules — Non-Negotiable

```
1. NORT Bot runs ONLY for /advice and /premium_advice
   → Never for /trending, /signals, /market, /portfolio, /papertrade

2. EXECUTION_MODE=PAPER always
   → No real trades. No real money. No real blockchain writes.
   → COMMIT_TX is optional for demo receipts on Polygon testnet only.

3. Backend verifies all payment proofs
   → The bot never trusts the user's claim of payment
   → Always goes through POST /x402/verify

4. Every signal must have a reason string
   → A score without an explanation is not acceptable

5. Every advice response must have a disclaimer
   → "This is not financial advice. Paper mode only."

6. Everything runs locally
   → One docker-compose up and the full system is running
```

---

## How The Team's Work Connects

```
Intern 1 (Markets)
   └──→ populates Market table in SQLite
         │
         └──→ Intern 2 (Signals) reads Market table
                └──→ scores, ranks, writes AISignal table
                      │
                      ├──→ Intern 4 (Bot) serves /signals command
                      ├──→ Intern 6 (Dashboard) shows Signals page
                      └──→ Intern 3 (NORT Bot) calls get_signals() for advice
                                  │
                                  └──→ Intern 4 (Bot) serves /advice command
                                        │
                                        └──→ Intern 4 (x402) gates /premium_advice

Intern 5 (Paper Trading)
   └──→ writes Trade table
         │
         ├──→ Intern 4 (Bot) serves /papertrade command
         ├──→ Intern 6 (Dashboard) shows Trades + Wallet pages
         └──→ Intern 3 (NORT Bot) calls get_wallet_summary() for advice context
```

Every intern's work feeds at least two other interns. Nothing is isolated. If one piece is missing, multiple things break downstream.

---

## File Map — Where Everything Lives

```
polymarket-ai-assistant/
│
├── apps/
│   ├── telegram-bot/
│   │   ├── main.py          ← bot startup, registers all command handlers
│   │   └── commands.py      ← /trending /signals /advice /pay /papertrade logic
│   │
│   └── dashboard/
│       └── src/
│           ├── app/         ← Next.js pages (overview, markets, signals, wallet...)
│           ├── components/  ← SignalCard, MarketCard, TradeRow UI components
│           └── lib/         ← API fetchers that call the FastAPI backend
│
├── services/
│   ├── backend/
│   │   ├── main.py          ← FastAPI app, registers all routers
│   │   ├── api/
│   │   │   ├── markets.py   ← GET /markets, GET /market/{id}
│   │   │   ├── signals.py   ← GET /signals?top=20          ← INTERN 2
│   │   │   └── trades.py    ← POST /papertrade, GET /wallet/summary
│   │   ├── core/
│   │   │   ├── signals_engine.py  ← all scoring logic     ← INTERN 2
│   │   │   └── x402_verifier.py   ← payment proof checker
│   │   └── data/
│   │       ├── models.py    ← User, Market, AISignal, Payment, Trade tables
│   │       └── database.py  ← SQLite connection, init_db()
│   │
│   └── agent/
│       ├── skills/          ← get_market(), get_signals(), get_wallet_summary()
│       ├── agent.json       ← OpenRouter config (model, api key env var)
│       └── prompt_templates.py ← builds structured prompts for NORT Bot
│
└── data/
    └── assistant.db         ← the single SQLite database file
```

---

*Built for Friday demo. Paper trading only. EXECUTION_MODE=PAPER.*
