import "./globals.css";
import Script from "next/script";
import Providers from "./providers";
import AuthSync from "./components/AuthSync";
import { AchievementProvider } from "./components/AchievementContext";
import { TradingModeProvider } from "./components/TradingModeContext";
// P-GLOBAL CHAT: Import floating chat button — renders on every page via layout
import GlobalChatButton from "./components/GlobalChatButton";
// MINI APP: Base/Farcaster MiniApp SDK initialisation
import MiniKitProvider from "./components/MiniKitProvider";

export default function RootLayout({ children }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <Script src="https://telegram.org/js/telegram-web-app.js" strategy="afterInteractive" />
        <MiniKitProvider>
        <Providers>
          <AchievementProvider>
            {/* TradingModeProvider fetches mode from backend on login and
                makes it available to Navbar (pill) and all trade screens */}
            <TradingModeProvider>
              <AuthSync />
              {children}
              {/* P-GLOBAL CHAT: Floating chat FAB mounts here so it persists across all page navigations */}
              <GlobalChatButton />
            </TradingModeProvider>
          </AchievementProvider>
        </Providers>
        </MiniKitProvider>
      </body>
    </html>
  );
}
