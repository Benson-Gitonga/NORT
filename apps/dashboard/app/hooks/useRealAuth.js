"use client";
import { useEffect, useState, useCallback } from "react";
import { usePrivy, useWallets } from "@privy-io/react-auth";
import { useTelegram } from "./useTelegram";

const BASE_CHAIN_ID = 8453;           // Base mainnet
const BASE_CHAIN_ID_HEX = "0x2105";  // 8453 in hex — used by MetaMask eth_chainId

export function useRealAuth() {
  const {
    ready: privyReady,
    authenticated,
    user,
    login: privyLogin,
    logout: privyLogout,
  } = usePrivy();
  const { wallets } = useWallets();
  const { user: tgUser } = useTelegram();

  const [initialized, setInitialized] = useState(false);
  const [chainSwitchError, setChainSwitchError] = useState(null);

  useEffect(() => { setInitialized(true); }, []);

  // ─── FIND THE RIGHT WALLET ─────────────────────────────────────────────────
  // Privy embedded wallet (created by Privy for Google/email users)
  const embeddedWallet = wallets?.find(w => w.walletClientType === "privy");

  // External wallet (MetaMask, Coinbase, Rainbow etc.)
  const externalWallet = wallets?.find(w => w.walletClientType !== "privy");

  // Active wallet: prefer embedded (it will be on Base), fall back to external
  const activeWallet = embeddedWallet || externalWallet || null;
  const privyWalletAddress = activeWallet?.address || null;

  // ─── FORCE BASE CHAIN ON ALL WALLETS ──────────────────────────────────────
  // This runs whenever wallets change (new connection, page load).
  // For embedded wallets: Privy's switchChain migrates the wallet to Base.
  // For external wallets: sends wallet_switchEthereumChain to MetaMask.
  const switchToBase = useCallback(async (wallet) => {
    if (!wallet) return;
    try {
      // Check current chain first to avoid unnecessary prompts
      const currentChainId = wallet.chainId; // format: "eip155:8453" or just number
      const currentId = typeof currentChainId === "string"
        ? parseInt(currentChainId.replace("eip155:", ""))
        : currentChainId;

      if (currentId === BASE_CHAIN_ID) return; // Already on Base

      await wallet.switchChain(BASE_CHAIN_ID);
      setChainSwitchError(null);
    } catch (err) {
      // Don't block the app if chain switch fails — just log it
      // MetaMask will show its own error if user rejects
      console.warn("[useRealAuth] Chain switch to Base failed:", err?.message);
      setChainSwitchError(err?.message || "Chain switch failed");
    }
  }, []);

  // Switch ALL connected wallets to Base when they appear
  useEffect(() => {
    if (!wallets?.length || !authenticated) return;
    wallets.forEach(w => switchToBase(w));
  }, [wallets, authenticated, switchToBase]);

  // Persist wallet address to localStorage for lib/api.js
  useEffect(() => {
    if (!privyWalletAddress) return;
    try {
      window.localStorage.setItem("walletAddress", privyWalletAddress.toLowerCase());
    } catch {}
  }, [privyWalletAddress]);

  const walletAddress =
    privyWalletAddress || (tgUser ? `tg_${tgUser.id}` : null);

  const isAuthed =
    !!privyReady && initialized && (!!authenticated || !!tgUser);

  const logout = async () => {
    try { await privyLogout(); } catch {}
    try {
      window.localStorage.removeItem("walletAddress");
      window.localStorage.removeItem("nort_auth");
      window.localStorage.removeItem("nort_username");
    } catch {}
    window.location.href = "/";
  };

  // ─── WALLET TYPE ──────────────────────────────────────────────────────────
  const walletType = embeddedWallet
    ? "embedded"   // Privy-managed, on Base
    : externalWallet
    ? "external"   // MetaMask / Coinbase / Rainbow (switched to Base above)
    : tgUser
    ? "telegram"
    : null;

  // ─── CHAIN STATUS ─────────────────────────────────────────────────────────
  const activeChainId = activeWallet?.chainId
    ? parseInt(String(activeWallet.chainId).replace("eip155:", ""))
    : null;
  const isOnBase = activeChainId === BASE_CHAIN_ID;

  const combinedUser = user
    ? {
        id:           user.id,
        privyUserId:  user.id,
        firstName:
          user.google?.name?.split(" ")[0] ||
          user.email?.address?.split("@")[0] ||
          null,
        name:   user.google?.name  || user.email?.address  || null,
        email:  user.email?.address || user.google?.email  || null,
        walletAddress,
        walletType,
        isOnBase,
      }
    : tgUser
    ? {
        id:          tgUser.id?.toString(),
        privyUserId: null,
        firstName:   tgUser.first_name || null,
        name:        tgUser.first_name || null,
        email:       null,
        walletAddress,
        walletType:  "telegram",
        isOnBase:    null,
      }
    : null;

  return {
    ready:           !!privyReady && initialized,
    isAuthed,
    user:            combinedUser,
    walletAddress,
    walletType,
    isOnBase,
    activeChainId,
    chainSwitchError,
    switchToBase:    () => switchToBase(activeWallet),
    login:           privyLogin,
    logout,
  };
}
