"use client";
import { useEffect, useRef } from "react";
import { useAuth } from "@/hooks/useAuth";

export default function AuthSync() {
  const { isAuthed, walletAddress } = useAuth();
  const didSync = useRef(false);

  useEffect(() => {
    if (!isAuthed || !walletAddress || didSync.current) return;
    didSync.current = true;

    try {
      if (typeof window !== "undefined") {
        window.localStorage.setItem("walletAddress", walletAddress);
      }
    } catch {}

    const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    // Register wallet and initialize paper balance if needed.
    // We use wallet_address as telegram_id for dashboard users (no real Telegram ID).
    fetch(`${BASE}/api/wallet/connect`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        wallet_address: walletAddress,
        telegram_id: walletAddress.toLowerCase(),
      }),
    }).then(r => r.json()).then(d => {
      console.log("[AuthSync] wallet connected:", d);
    }).catch((e) => {
      console.warn("[AuthSync] wallet connect failed:", e);
    });
  }, [isAuthed, walletAddress]);

  return null;
}
