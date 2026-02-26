"use client";
import { useEffect, useRef, useState } from "react";
import { useAuth } from "@/hooks/useAuth";
import { BASE } from "@/lib/api";

export default function AuthSync() {
  const { isAuthed, walletAddress } = useAuth();
  const didSync = useRef(false);

  const [showUsername, setShowUsername] = useState(false);
  const [username, setUsername]         = useState("");
  const [saving, setSaving]             = useState(false);

  useEffect(() => {
    if (!isAuthed || !walletAddress || didSync.current) return;
    didSync.current = true;

    // Step 1: Register/ensure the wallet exists in the DB (idempotent).
    // Do NOT send telegram_id — the UNIQUE constraint causes errors for
    // returning users. The wallet_address is the primary key for dashboard users.
    fetch(`${BASE}/api/wallet/connect`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ wallet_address: walletAddress.toLowerCase() }),
    })
      .then(r => r.json())
      .then(data => {
        // Step 2: Check if this user already has a username in the DB.
        // The wallet/connect response includes username.
        const existingUsername = data?.username || null;

        // Also check localStorage cache so we don't re-prompt on every reload.
        const cachedUsername = (() => {
          try { return window.localStorage.getItem("nort_username"); } catch { return null; }
        })();

        if (existingUsername) {
          // User has a username — cache it locally so we know next time
          try { window.localStorage.setItem("nort_username", existingUsername); } catch {}
        } else if (!cachedUsername) {
          // New user with no username anywhere — show the prompt once
          setShowUsername(true);
        }
      })
      .catch(e => console.warn("[AuthSync] register failed:", e));
  }, [isAuthed, walletAddress]);

  const saveUsername = async () => {
    if (!username.trim() || !walletAddress) return;
    setSaving(true);
    try {
      await fetch(`${BASE}/api/wallet/connect`, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          wallet_address: walletAddress.toLowerCase(),
          username:       username.trim(),
        }),
      });
      // Cache locally so the prompt never reappears
      try { window.localStorage.setItem("nort_username", username.trim()); } catch {}
      setShowUsername(false);
    } catch (e) {
      console.warn("[AuthSync] username save failed:", e);
    } finally {
      setSaving(false);
    }
  };

  const skipUsername = () => {
    // Mark as "skipped" in localStorage so we don't re-prompt on reload.
    // They can always set a username later from the Profile page.
    try { window.localStorage.setItem("nort_username", "__skipped__"); } catch {}
    setShowUsername(false);
  };

  if (!showUsername) return null;

  return (
    <div className="modal-overlay" style={{ zIndex: 9999 }}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <div className="modal-handle" />
        <div className="modal-title">Welcome to NORT 👋</div>
        <div className="modal-sub">Choose a username for the leaderboard</div>
        <div className="modal-input-wrap" style={{ marginTop: 16 }}>
          <input
            className="modal-input"
            type="text"
            placeholder="e.g. whale_hunter"
            value={username}
            onChange={e => setUsername(e.target.value)}
            maxLength={24}
            onKeyDown={e => e.key === "Enter" && saveUsername()}
            autoFocus
          />
        </div>
        <button
          className="modal-cta"
          onClick={saveUsername}
          disabled={!username.trim() || saving}
          style={{ marginTop: 12 }}
        >
          {saving ? "Saving..." : "Set Username"}
        </button>
        <button
          className="chip-btn"
          onClick={skipUsername}
          style={{ width: "100%", marginTop: 8, opacity: 0.6 }}
        >
          Skip for now
        </button>
      </div>
    </div>
  );
}
