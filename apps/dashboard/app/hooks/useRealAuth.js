"use client";
import { useEffect, useState } from "react";
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

  useEffect(() => {
    if (typeof window === "undefined") return;
    const handleUnload = () => {
      try {
        window.localStorage.removeItem("walletAddress");
        window.localStorage.removeItem("nort_auth");
      } catch {}
    };
    window.addEventListener("beforeunload", handleUnload);
    return () => window.removeEventListener("beforeunload", handleUnload);
  }, []);

  const walletAddress = forceLoggedOut ? null : (wallets?.[0]?.address || lsWallet || null);
  const isAuthed = !!privyReady && initialized && !forceLoggedOut && (!!authenticated || !!walletAddress);

  const logout = async () => {
    try {
      if (typeof window !== "undefined") {
        localStorage.removeItem("walletAddress");
        localStorage.removeItem("nort_auth");
      }
    } catch(e) {
      console.warn("[Auth] localStorage error:", e);
    }
    try {
      await privyLogout();
    } catch(e) {
      console.warn("[Auth] privyLogout error:", e);
    }
    if (typeof window !== "undefined") {
      window.location.replace(window.location.origin + "/");
    }
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
