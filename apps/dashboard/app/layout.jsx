import "./globals.css";
import Script from "next/script";
import Providers from "./providers";
import AuthSync from "./components/AuthSync";
import { AchievementProvider } from "./components/AchievementContext";
import { TradingModeProvider } from "./components/TradingModeContext";

export default function RootLayout({ children }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <Script src="https://telegram.org/js/telegram-web-app.js" strategy="afterInteractive" />
        <Providers>
          <AchievementProvider>
            {/* TradingModeProvider fetches mode from backend on login and
                makes it available to Navbar (pill) and all trade screens */}
            <TradingModeProvider>
              <AuthSync />
              {children}
            </TradingModeProvider>
          </AchievementProvider>
        </Providers>
      </body>
    </html>
  );
}
