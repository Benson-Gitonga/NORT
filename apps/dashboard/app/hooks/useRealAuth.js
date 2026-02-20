"use client";
import { useEffect, useState, useRef } from "react";
import { usePrivy, useWallets } from "@privy-io/react-auth";
import { useTelegram } from "./useTelegram";

export function useRealAuth() {
  const { ready: privyReady, authenticated, user, login: privyLogin, logout: privyLogout } = usePrivy();
  const { wallets } = useWallets();
  const { user: tgUser } = useTelegram();
  const [lsWallet, setLsWallet] = useState(null);
  const [initialized, setInitialized] = useState(false);
  const [forceLoggedOut, setForceLoggedOut] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const w = window.localStorage.getItem("walletAddress");
    const forceOut = window.localStorage.getItem("force_logout");
    if (w) setLsWallet(w);
    if (forceOut === "true") {
      setForceLoggedOut(true);
      window.localStorage.removeItem("force_logout");
    }
    setInitialized(true);
  }, []);

  const walletAddress = forceLoggedOut ? null : (wallets?.[0]?.address || lsWallet || null);

  const isAuthed = !!privyReady && initialized && !forceLoggedOut && (!!authenticated || !!walletAddress);

  const logout = async () => {
    console.log("[Auth] logout called");
    try {
      if (typeof window !== "undefined") {
        localStorage.removeItem("walletAddress");
        localStorage.removeItem("nort_auth");
        localStorage.setItem("force_logout", "true");
        console.log("[Auth] localStorage cleared");
      }
    } catch(e) {
      console.log("[Auth] localStorage error:", e);
    }
    try {
      await privyLogout();
    } catch(e) {
      console.log("[Auth] privyLogout error:", e);
    }
    window.location.replace(window.location.origin + "/?t=" + Date.now());
  };

  return {
    ready: !!privyReady && initialized,
    isAuthed,
    user: user || null,
    walletAddress,
    login: privyLogin,
    logout,
  };
}
