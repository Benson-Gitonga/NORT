import "./globals.css";
import Script from "next/script";
import Providers from "./providers";
import AuthSync from "./components/AuthSync";
import { AchievementProvider } from "./components/AchievementContext";
export default function RootLayout({ children }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <Script src="https://telegram.org/js/telegram-web-app.js" strategy="afterInteractive" />
        <Providers>
          <AuthSync />
          <AchievementProvider>
            {children}
          </AchievementProvider>
        </Providers>
      </body>
    </html>
  );
}
