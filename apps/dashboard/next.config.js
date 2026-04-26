// next.config.js in your Main NORT Repo
/** @type {import('next').NextConfig} */
const path = require('path');

const isDev = process.env.NODE_ENV === 'development';

const nextConfig = {
  turbopack: {
    root: path.resolve(__dirname),
  },

  async rewrites() {
    // In development, serve everything locally.
    // Only proxy landing assets to Vercel in production.
    if (isDev) return [];

    return [
      {
        // Bridges landing page assets (CSS/JS) from Vercel in production only
        source: '/_next/:path*',
        destination: 'https://nort-landing-nine.vercel.app/_next/:path*',
      },
    ];
  },
};

module.exports = nextConfig;
