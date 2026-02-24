🤖 Polymarket AI Assistant

A powerful prediction market companion that combines real-time data, quantitative signals, and agentic AI insights. This system allows users to track Polymarket trends and receive premium AI-generated trading advice gated by x402 micro-payments.

📐 System Architecture
Our system is split into two distinct execution lanes to optimize for speed and cost:

🏎️ The Fast Path (Normal Commands)
Direct backend execution for high-frequency data.

Flow: Telegram → FastAPI → SQLite Cache → Response

Commands: /trending, /market <id>, /signals, /portfolio, /papertrade

🧠 The Agent Path (Advice Commands)
Agentic AI reasoning for deep market analysis.

Flow: Telegram → x402 Verify → OpenClaw (OpenRouter) → Response
