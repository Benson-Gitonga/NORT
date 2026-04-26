"use client";
import { useState, useCallback, useEffect } from "react";

const MOCK_USER = {
  id: "mock_user_01",
  telegram: { username: "nortuser", firstName: "NJ" },
  wallet: { address: "0xMock...1234" },
};

export function useMockAuth() {
  const [isAuthed, setIsAuthed] = useState(false);
  const [ready, setReady] = useState(false);
  const [isLoggingOut, setIsLoggingOut] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const stored = localStorage.getItem("nort_auth");
    if (stored === "true") {
      setIsAuthed(true);
    }
    setReady(true);
  }, []);

  const login = useCallback(() => {
    setIsAuthed(true);
    if (typeof window !== "undefined") {
      localStorage.setItem("nort_auth", "true");
    }
  }, []);

  const logout = useCallback(() => {
    setIsLoggingOut(true);
    setIsAuthed(false);
    if (typeof window !== "undefined") {
      localStorage.removeItem("nort_auth");
    }
    window.location.href = "/";
  }, []);

  return {
    ready,
    isAuthed,
    user: isAuthed ? MOCK_USER : null,
    walletAddress: isAuthed ? MOCK_USER.wallet.address : null,
    login,
    logout,
    isLoggingOut,
  };
}