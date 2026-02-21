import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Increase the proxy timeout to 120 s to accommodate long Gemini extractions.
  // Default is ~30 s which causes ECONNRESET on document uploads.
  experimental: {
    proxyTimeout: 120_000,
  },

  // Proxy all /api/* requests to the FastAPI backend in dev.
  // This eliminates CORS issues entirely — the browser never makes cross-origin requests.
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://localhost:8000/api/:path*",
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
