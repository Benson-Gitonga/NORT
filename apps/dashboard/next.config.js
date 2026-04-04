// next.config.js in your Main NORT Repo
/** @type {import('next').NextConfig} */
const path = require('path');

const nextConfig = {
  turbopack: {
    root: path.resolve(__dirname),
  },

  async rewrites() {
    // DO NOT include a rewrite for source: '/' here. The middleware handles it.
    return [
      {
        // This is necessary to bridge the landing page assets (CSS/JS)
        source: '/_next/:path*',
        destination: 'https://nort-landing-nine.vercel.app/_next/:path*',
      },
    ];
  },
};

module.exports = nextConfig;