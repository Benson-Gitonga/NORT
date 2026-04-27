/**
 * Farcaster / Base Mini App Manifest
 *
 * Served at: GET /.well-known/farcaster.json
 *
 * The `accountAssociation` block is intentionally empty here.
 * You will fill it in after running the Base Build verification tool:
 *   https://www.base.dev/preview?tab=account
 *
 * Steps:
 *  1. Deploy the app so this route is publicly reachable.
 *  2. Go to base.dev/preview → Account association tab.
 *  3. Enter your domain, click Submit → Verify, sign with your Base Account.
 *  4. Copy the three generated values into accountAssociation below.
 *  5. Re-deploy.
 */

const ROOT_URL = process.env.NEXT_PUBLIC_URL;

export async function GET() {
  return Response.json({
    accountAssociation: {
      // ⬇ Paste values from base.dev/preview after verification
      header: "",
      payload: "",
      signature: "",
    },
    miniapp: {
      version: "1",
      name: "NORT",
      subtitle: "AI Prediction Market Signals",
      description:
        "NORT is an AI-powered Polymarket trading assistant. Get hot signals, copy top traders, and execute paper trades with USDC micropayments on Base.",
      homeUrl: ROOT_URL,
      iconUrl: `${ROOT_URL}/icon.png`,
      splashImageUrl: `${ROOT_URL}/splash.png`,
      splashBackgroundColor: "#0a0a0a",
      webhookUrl: `${ROOT_URL}/api/miniapp/webhook`,
      screenshotUrls: [
        `${ROOT_URL}/screenshots/feed.jpeg`,
        `${ROOT_URL}/screenshots/signals.jpeg`,
        `${ROOT_URL}/screenshots/wallet.jpeg`,
      ],
      primaryCategory: "finance",
      tags: ["trading", "polymarket", "AI", "signals", "USDC", "predictions"],
      heroImageUrl: `${ROOT_URL}/hero.png`,
      tagline: "Trade smarter with AI signals",
      ogTitle: "NORT — AI Prediction Market Signals",
      ogDescription:
        "Hot Polymarket signals powered by AI. Paper trade, copy top traders, earn on Base.",
      ogImageUrl: `${ROOT_URL}/og.png`,
    },
  });
}
