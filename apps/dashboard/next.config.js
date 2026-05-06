// next.config.js
/** @type {import('next').NextConfig} */
const path = require('path');

const isDev = process.env.NODE_ENV === 'development';

const nextConfig = {
  turbopack: {
    root: path.resolve(__dirname),

    // ── Resolve @/* alias explicitly for Turbopack ──────────────────────────
    // jsconfig.json defines @/* → ./app/* but Turbopack needs the alias
    // declared here too, or it fails to resolve @/ imports in built chunks.
    resolveAlias: {
      '@': path.resolve(__dirname, 'app'),
    },
  },

  async headers() {
    return [
      {
        // Allow the Base app and Farcaster to read the manifest
        source: '/.well-known/farcaster.json',
        headers: [
          { key: 'Access-Control-Allow-Origin', value: '*' },
          { key: 'Content-Type', value: 'application/json' },
        ],
      },
    ];
  },

  async rewrites() {
    // In development, serve everything locally.
    // Only proxy landing assets to Vercel in production.
    // DO NOT include a rewrite for source: '/' here — proxy.ts handles it.
    if (isDev) return [];

    return [
      {
        // Bridge landing page assets (CSS/JS chunks) from the external Vercel deploy
        source: '/_next/:path*',
        destination: 'https://nort-landing-nine.vercel.app/_next/:path*',
      },
    ];
  },
};

module.exports = nextConfig;
