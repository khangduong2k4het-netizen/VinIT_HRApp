/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // VPS/PM2 runs `next start` directly from this directory. Standalone output
  // is opt-in for the Docker image, which sets NEXT_OUTPUT_STANDALONE=1.
  ...(process.env.NEXT_OUTPUT_STANDALONE === '1'
    ? { output: 'standalone' }
    : {}),
};

module.exports = nextConfig;
