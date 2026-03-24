/** @type {import('next').NextConfig} */
const path = require('path');

const nextConfig = {
  // Your existing Turbopack config
  turbopack: {
    root: path.resolve(__dirname),
  },

  // The "Gateway" logic for your Multi-Zone setup
  async rewrites() {
    return [
      {
        // When a user hits the homepage (nortapp.online/)
        source: '/',
        // Show them the content from your separate landing page repo
        destination: 'https://nort-landing-nine.vercel.app',
      },
      {
        // This ensures the landing page's CSS, JS, and images load correctly
        source: '/_next/:path*',
        destination: 'https://nort-landing-nine.vercel.app/_next/:path*',
      },
    ];
  },
};

module.exports = module.exports = nextConfig;