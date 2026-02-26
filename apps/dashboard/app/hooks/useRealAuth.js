"use client";
import { useEffect, useState, useRef } from "react";
import { usePrivy, useWallets } from "@privy-io/react-auth";
import { useTelegram } from "./useTelegram";

export function useRealAuth() {
  const { ready: privyReady, authenticated, user, login: privyLogin, logout: privyLogout } = usePrivy();
  const { wallets } = useWallets(); // correct destructure — returns { wallets: [] }
  const { user: tgUser } = useTelegram();

  const [initialized, setInitialized] = useState(false);
  const [lsWallet, setLsWallet]       = useState(null);

  // On mount: load persisted wallet from localStorage
  useEffect(() => {
    if (typeof window === "undefined") return;
    const stored = window.localStorage.getItem("walletAddress");
    if (stored) setLsWallet(stored);
    setInitialized(true);
  }, []);

  // Persist wallet address whenever Privy gives us one
  useEffect(() => {
    if (!wallets || wallets.length === 0) return;
    const addr = wallets[0]?.address;
    if (!addr) return;
    try {
      window.localStorage.setItem("walletAddress", addr);
      setLsWallet(addr);
    } catch {}
  }, [wallets]);

  // Clear on page unload so sessions don't leak between users
  // NOTE: we do NOT remove walletAddress here — logout handles that explicitly.
  // Removing it on unload races with Privy's own logout flow.
  useEffect(() => {
    if (typeof window === "undefined") return;
    const handleUnload = () => {
      try {
        window.localStorage.removeItem("nort_auth");
      } catch {}
    };
    window.addEventListener("beforeunload", handleUnload);
    return () => window.removeEventListener("beforeunload", handleUnload);
  }, []);

  // Best wallet address: prefer live Privy wallet, fall back to localStorage
  const privyWalletAddress = wallets?.[0]?.address || null;
  const walletAddress = privyWalletAddress || lsWallet || null;

  const isAuthed = !!privyReady && initialized && (!!authenticated || !!walletAddress || !!tgUser);

  const logout = async () => {
    // 1. Sign out from Privy first, before clearing storage
    try { await privyLogout(); } catch {}
    // 2. Clear local state after Privy is done
    try {
      window.localStorage.removeItem("walletAddress");
      window.localStorage.removeItem("nort_auth");
    } catch {}
    // 3. Hard redirect to root to reset all React state
    if (typeof window !== "undefined") {
      window.location.href = "/";
    }
  };

  // Build a consistent user object regardless of login method
  const combinedUser = user
    ? {
        id:           user.id,
        firstName:    user.google?.name?.split(" ")[0]
                      || user.email?.address?.split("@")[0]
                      || "User",
        name:         user.google?.name || user.email?.address || "User",
        displayName:  user.google?.name || user.email?.address || "User",
        email:        user.email?.address || user.google?.email || null,
        walletAddress,
      }
    : tgUser
    ? {
        id:           tgUser.id?.toString(),
        firstName:    tgUser.first_name,
        name:         tgUser.first_name,
        displayName:  tgUser.first_name,
        email:        null,
        walletAddress,
      }
    : null;

  return {
    ready:         !!privyReady && initialized,
    isAuthed,
    user:          combinedUser,
    walletAddress,
    login:         privyLogin,
    logout,
  };
}
