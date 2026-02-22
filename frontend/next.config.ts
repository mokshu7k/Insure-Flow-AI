import type { NextConfig } from "next";

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  // Proxy all /api/* requests to the FastAPI backend.
  // In dev → localhost:8000, in prod → Cloud Run URL (set via env var in Vercel).
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${BACKEND_URL}/api/:path*`,
      },
    ];
  },
  // Increase the proxy timeout to 2 minutes so long-running backend calls
  // (e.g. AI extraction) don't cause ECONNRESET in the browser.
  experimental: {
    proxyTimeout: 120_000,
  },
};

export default nextConfig;
