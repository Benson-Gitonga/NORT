import "./globals.css";
import Script from "next/script";
import Providers from "./providers";
import AuthSync from "./components/AuthSync";
import { AchievementProvider } from "./components/AchievementContext";
import { TradingModeProvider } from "./components/TradingModeContext";

export default function RootLayout({ children }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        {/* Google Fonts — used by landing page sections */}
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;500;600;700;800&family=Plus+Jakarta+Sans:wght@300;400;500;600;700&family=Goldman:wght@400;500;700&family=Space+Grotesk:wght@400;500;600;700&display=swap" rel="stylesheet" />
        {/* Iconify — used by landing page feature cards */}
        <script src="https://code.iconify.design/iconify-icon/1.0.7/iconify-icon.min.js" async></script>
      </head>
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
