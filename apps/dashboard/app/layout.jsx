import "./globals.css";
import Script from "next/script";
import Providers from "./providers";
import AuthSync from "./components/AuthSync";
import { AchievementProvider } from "./components/AchievementContext";
import { TradingModeProvider } from "./components/TradingModeContext";
import GlobalChatButton from "./components/GlobalChatButton";
import MiniKitProvider from "./components/MiniKitProvider";

// This is how you add the meta tag in Next.js App Router
export const metadata = {
  other: {
    "base:app_id": "69ef725c7e92b7a4af93efb6",
  },
};

export const metadata = {
  other: {
    'base:app_id': '69efacf4f464a4292f34e647',
  },
};


export default function RootLayout({ children }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <Script 
          src="https://telegram.org/js/telegram-web-app.js" 
          strategy="afterInteractive" 
        />
        <MiniKitProvider>
          <Providers>
            <AchievementProvider>
              <TradingModeProvider>
                <AuthSync />
                {children}
                <GlobalChatButton />
              </TradingModeProvider>
            </AchievementProvider>
          </Providers>
        </MiniKitProvider>
      </body>
    </html>
  );
}