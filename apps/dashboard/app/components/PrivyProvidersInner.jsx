"use client";
import { PrivyProvider, usePrivy } from "@privy-io/react-auth";
import { base, polygon } from "viem/chains";
import { useEffect } from "react";
import { TokenStore } from "@/lib/tokenStore";

/**
 * TokenRegistrar — inner component that lives inside PrivyProvider.
 * Registers the real getAccessToken function into TokenStore
 * the moment Privy is ready, so lib/api.js can call it without hooks.
 */
function TokenRegistrar() {
  const { getAccessToken, ready } = usePrivy();

  useEffect(() => {
    if (ready && getAccessToken) {
      TokenStore.set(getAccessToken);
    }
  }, [ready, getAccessToken]);

  return null;
}

export default function PrivyProvidersInner({ children }) {
  const appId = process.env.NEXT_PUBLIC_PRIVY_APP_ID || "";

  return (
    <PrivyProvider
      appId={appId}
      config={{
        // ─── CHAIN CONFIG ─────────────────────────────────────────────────
        defaultChain: base,
        supportedChains: [base, polygon],

        // ─── LOGIN METHODS ────────────────────────────────────────────────
        loginMethods: ["google", "wallet", "email"],

        // ─── EMBEDDED WALLETS ─────────────────────────────────────────────
        embeddedWallets: {
          createOnLogin: "users-without-wallets",
          requireUserPasswordOnCreate: false,
          showWalletUIs: true,
        },

        // ─── EXTERNAL WALLETS ─────────────────────────────────────────────
        externalWallets: {
          coinbaseWallet: {
            connectionOptions: "smartWalletOnly",
          },
        },

        // ─── APPEARANCE ───────────────────────────────────────────────────
        appearance: {
          theme: "dark",
          accentColor: "#00A99D",
          walletList: ["metamask", "coinbase_wallet", "rainbow"],
        },
      }}
    >
      {/* Registers getAccessToken into TokenStore once Privy is ready */}
      <TokenRegistrar />
      {children}
    </PrivyProvider>
  );
}
