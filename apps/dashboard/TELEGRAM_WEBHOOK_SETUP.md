# Telegram Webhook Setup

This Vercel app now exposes a Telegram webhook route at:

`/api/telegram/webhook`

## Required Vercel Environment Variables

- `BOT_TOKEN`
- `TELEGRAM_WEBHOOK_SECRET`
- `TELEGRAM_BOT_USERNAME`
- `NEXT_PUBLIC_API_URL`

Optional:

- `TELEGRAM_BACKEND_URL`

`TELEGRAM_BACKEND_URL` is used by the webhook first. If it is not set, the route falls back to `NEXT_PUBLIC_API_URL`.

## Register The Webhook

Replace `<your-vercel-domain>` and the placeholders below:

```bash
curl -X POST "https://api.telegram.org/bot<BOT_TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d "{\"url\":\"https://<your-vercel-domain>/api/telegram/webhook\",\"secret_token\":\"<TELEGRAM_WEBHOOK_SECRET>\"}"
```

## Check Webhook Status

```bash
curl "https://api.telegram.org/bot<BOT_TOKEN>/getWebhookInfo"
```

## Notes

- The webhook route is implemented in [route.js](/C:/Users/laura/NORT/apps/dashboard/app/api/telegram/webhook/route.js).
- User language, pending premium state, and auto-trade settings are stored via the backend Telegram endpoints, so the webhook does not rely on in-memory state.
- The current implementation mirrors the existing Java bot command set for `/start`, `/lang`, `/signals`, `/trending`, `/advice`, `/pay`, `/portfolio`, `/markets`, `/papertrade`, and the auto-trade controls.
