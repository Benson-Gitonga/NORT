"use client";
<<<<<<< HEAD
import { useEffect, useState } from "react";
=======
import { useEffect, useState, useRef } from "react";
>>>>>>> cb9d82afafe3ae19e7383359b11d2847e14f3853
import { usePrivy, useWallets } from "@privy-io/react-auth";
import { useTelegram } from "./useTelegram";

export function useRealAuth() {
<<<<<<< HEAD
  const { ready: privyReady, authenticated, user, login: privyLogin, logout: privyLogout } = usePrivy();
=======
  const { ready: privyReady, authenticated, user: privyUser, login: privyLogin, logout: privyLogout } = usePrivy();
>>>>>>> cb9d82afafe3ae19e7383359b11d2847e14f3853
  const { wallets } = useWallets();
  const { user: tgUser } = useTelegram();
  const [lsWallet, setLsWallet] = useState(null);
  const [initialized, setInitialized] = useState(false);
<<<<<<< HEAD
  const [forceLoggedOut, setForceLoggedOut] = useState(false);
=======
  const logoutInProgress = useRef(false);
>>>>>>> cb9d82afafe3ae19e7383359b11d2847e14f3853

  useEffect(() => {
    if (typeof window === "undefined") return;
    const w = window.localStorage.getItem("walletAddress");
<<<<<<< HEAD
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
=======
    if (w) setLsWallet(w);
    setInitialized(true);
  }, []);

  // Get wallet address - prefer connected wallet, fallback to localStorage
  const walletAddress = wallets?.[0]?.address || lsWallet || null;
  
  // Build combined user object
  const user = privyUser || (tgUser ? {
    id: tgUser.id?.toString(),
    firstName: tgUser.first_name,
    name: tgUser.first_name,
    displayName: tgUser.first_name,
    email: null,
    telegram: tgUser
  } : null);
  
  // Force not authenticated if logout is in progress
  const isAuthed = !logoutInProgress.current && !!privyReady && initialized && (!!authenticated || !!walletAddress);

  const logout = () => {
    if (logoutInProgress.current) {
      console.log("[Auth] Logout already in progress");
      return;
    }
    
    logoutInProgress.current = true;
    console.log("[Auth] Starting logout, redirecting to login...");
    
    // Clear ALL local storage
    if (typeof window !== "undefined") {
      try {
        for (let i = localStorage.length - 1; i >= 0; i--) {
          const key = localStorage.key(i);
          if (key && (key.includes('privy') || key.includes('wallet') || key.includes('auth') || key.includes('nort'))) {
            localStorage.removeItem(key);
          }
        }
      } catch (e) {
        console.log("[Auth] localStorage clear error:", e);
      }
    }
    
    // Try Privy logout
    try {
      privyLogout();
    } catch (e) {
      // Ignore errors
    }
    
    // Immediate redirect to home (which shows login)
    if (typeof window !== "undefined") {
      window.location.href = "/";
>>>>>>> cb9d82afafe3ae19e7383359b11d2847e14f3853
    }
  };

  return {
    ready: !!privyReady && initialized,
    isAuthed,
<<<<<<< HEAD
    user: user || null,
=======
    user,
>>>>>>> cb9d82afafe3ae19e7383359b11d2847e14f3853
    walletAddress,
    login: privyLogin,
    logout,
  };
}
