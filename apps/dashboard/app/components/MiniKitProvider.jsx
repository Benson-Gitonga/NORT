"use client";
/**
 * MiniKitProvider
 *
 * Initialises the Base/Farcaster MiniApp SDK as early as possible.
 * Calls sdk.actions.ready() once the app has mounted, which hides
 * the splash screen and signals to the Base app that NORT is live.
 *
 * Place this as a wrapper inside the root layout — it has no visible UI.
 */
import { useEffect } from "react";
import { sdk } from "@farcaster/miniapp-sdk";

export default function MiniKitProvider({ children }) {
  useEffect(() => {
    // Signal to the Base/Farcaster host that the app is ready to display.
    // Safe to call even when running outside the mini app context —
    // the SDK no-ops gracefully in a regular browser.
    sdk.actions.ready().catch(() => {});
  }, []);

  return <>{children}</>;
}
