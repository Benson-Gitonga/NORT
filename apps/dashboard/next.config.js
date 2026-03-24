/** @type {import('next').NextConfig} */
const path = require('path');

const nextConfig = {
  turbopack: {
    root: path.resolve(__dirname),
  },

  async rewrites() {
    return [
      {
        // Keep this! It's the "bridge" for the landing page's CSS/JS
        source: '/_next/:path*',
        destination: 'https://nort-landing-nine.vercel.app/_next/:path*',
      },
    ];
  },
};

module.exports = nextConfig;