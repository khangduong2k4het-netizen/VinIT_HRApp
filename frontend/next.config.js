/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Only for the synthetic preview server, never a production deployment.
  ...(process.env.DEMO_PREVIEW === '1' ? {
    allowedDevOrigins: ['*.e2b.app', '127.0.0.1'],
    async redirects() { return [{ source: '/', destination: '/demo', permanent: false }]; },
  } : {}),
  // VPS/PM2 runs `next start` directly from this directory. Standalone output
  // is opt-in for the Docker image, which sets NEXT_OUTPUT_STANDALONE=1.
  ...(process.env.NEXT_OUTPUT_STANDALONE === '1'
    ? { output: 'standalone' }
    : {}),
};

module.exports = nextConfig;
