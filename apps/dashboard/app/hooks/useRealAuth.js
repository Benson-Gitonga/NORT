"use client";
import { useEffect, useState } from "react";
import { usePrivy, useWallets } from "@privy-io/react-auth";
import { useTelegram } from "./useTelegram";

export function useRealAuth() {
  const { ready: privyReady, authenticated, user, login: privyLogin, logout: privyLogout } = usePrivy();
  const { wallets } = useWallets();
  const { user: tgUser } = useTelegram();

  const [initialized, setInitialized] = useState(false);

  // On mount: mark as initialized
  useEffect(() => {
    setInitialized(true);
  }, []);

  // Persist wallet address to localStorage whenever Privy gives us one
  // (api.js reads this for API calls)
  const privyWalletAddress = wallets?.[0]?.address || null;
  useEffect(() => {
    if (!privyWalletAddress) return;
    try { window.localStorage.setItem("walletAddress", privyWalletAddress); } catch {}
  }, [privyWalletAddress]);

  // walletAddress: only the live Privy wallet — do NOT fall back to localStorage.
  // Falling back to localStorage kept isAuthed=true after logout (stale value).
  const walletAddress = privyWalletAddress || (tgUser ? `tg_${tgUser.id}` : null);

  // isAuthed: Privy authenticated is the source of truth.
  const isAuthed = !!privyReady && initialized && (!!authenticated || !!tgUser);

  const logout = async () => {
    try { await privyLogout(); } catch {}
    try {
      window.localStorage.removeItem("walletAddress");
      window.localStorage.removeItem("nort_auth");
      window.localStorage.removeItem("nort_username");
    } catch {}
    window.location.href = "/";
  };

  const combinedUser = user
    ? {
        id:    user.id,
        firstName: user.google?.name?.split(" ")[0]
                   || user.email?.address?.split("@")[0]
                   || null,
        name:  user.google?.name || user.email?.address || null,
        email: user.email?.address || user.google?.email || null,
        walletAddress,
      }
    : tgUser
    ? {
        id:    tgUser.id?.toString(),
        firstName: tgUser.first_name || null,
        name:  tgUser.first_name || null,
        email: null,
        walletAddress,
      }
    : null;

  return {
    ready:        !!privyReady && initialized,
    isAuthed,
    user:         combinedUser,
    walletAddress,
    login:        privyLogin,
    logout,
  };
}
