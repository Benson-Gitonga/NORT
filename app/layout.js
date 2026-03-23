import './globals.css'

export const metadata = {
  metadataBase: new URL('https://nort.trade'),
  title: 'NORT — AI-Powered Prediction Market Signals',
  description: 'NORT makes Polymarket trading easy. A real-time signals engine ranks the best opportunities by momentum and volume — then lets you ask AI for a plain-English breakdown before you trade. Free to start.',

  alternates: {
    canonical: '/',
  },

  openGraph: {
    type: 'website',
    url: 'https://nort.trade',
    title: 'NORT — AI-Powered Prediction Market Signals',
    description: 'NORT makes Polymarket trading easy. A real-time signals engine ranks the best opportunities by momentum and volume — then lets you ask AI for a plain-English breakdown before you trade. Free to start.',
    siteName: 'NORT',
    images: [
      {
        url: '/images/og-image.png',
        width: 1200,
        height: 630,
        alt: 'NORT — AI Prediction Market Signals',
      },
    ],
  },

  twitter: {
    card: 'summary_large_image',
    title: 'NORT — AI-Powered Prediction Market Signals',
    description: 'NORT makes Polymarket trading easy. Real-time signals ranked by momentum and volume — ask AI for advice before you trade. Free to start.',
    images: ['/images/og-image.png'],
  },

  icons: {
    icon: '/favicon.ico',
    shortcut: '/favicon.ico',
    apple: '/apple-touch-icon.png',
  },

  robots: {
    index: true,
    follow: true,
  },
}

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;500;600;700;800&family=Plus+Jakarta+Sans:wght@300;400;500;600;700&family=Goldman:wght@400;500;700&family=Space+Grotesk:wght@400;500;600;700&display=swap" rel="stylesheet" />
        <script src="https://code.iconify.design/iconify-icon/1.0.7/iconify-icon.min.js" async></script>
        {/* JSON-LD structured data — helps Google show rich results */}
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify({
            "@context": "https://schema.org",
            "@type": "SoftwareApplication",
            "name": "NORT",
            "url": "https://nort.trade",
            "description": "NORT makes Polymarket trading easy. A real-time signals engine ranks the best opportunities by momentum and volume — then lets you ask AI for a plain-English breakdown before you trade.",
            "applicationCategory": "FinanceApplication",
            "operatingSystem": "Web",
            "offers": [
              { "@type": "Offer", "price": "0", "priceCurrency": "USD", "name": "Free — full access during beta" }
            ]
          })}}
        />
        {/* Skip-to-content styles — inline so they load with zero delay.
            The link is visually hidden by default, revealed on :focus.
            Using a <style> tag here avoids the need for a 'use client'
            directive on layout.js just for JS event handlers. */}
        <style>{`
          .skip-link {
            position: absolute;
            top: -999px;
            left: -999px;
            z-index: 9999;
            padding: 12px 20px;
            background: #00C896;
            color: #000;
            font-weight: 700;
            font-size: 14px;
            border-radius: 8px;
            text-decoration: none;
          }
          .skip-link:focus {
            top: 16px;
            left: 16px;
          }
        `}</style>
      </head>
      <body>
        <a href="#main-content" className="skip-link">
          Skip to main content
        </a>
        {children}
      </body>
    </html>
  )
}
