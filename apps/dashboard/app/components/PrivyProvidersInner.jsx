"use client";
import { PrivyProvider } from "@privy-io/react-auth";
import { base, polygon } from "viem/chains";

export default function PrivyProvidersInner({ children }) {
  const appId = process.env.NEXT_PUBLIC_PRIVY_APP_ID || "";

  return (
    <PrivyProvider
      appId={appId}
      config={{
        // ─── CHAIN CONFIG ─────────────────────────────────────────────────
        // defaultChain: Base — all embedded wallets are created on Base.
        // Polygon is supported for future Polymarket bridging (Phase 2).
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

        // ─── EXTERNAL WALLETS (MetaMask, Coinbase, Rainbow) ───────────────
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
      {children}
    </PrivyProvider>
  );
}
