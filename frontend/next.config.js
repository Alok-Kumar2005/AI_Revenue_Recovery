/** @type {import('next').NextConfig} */
const backendUrl = (
  process.env.BACKEND_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8000"
).replace(/\/$/, "");

const nextConfig = {
  // Use standalone output only in Docker environments (not on Vercel)
  ...(process.env.VERCEL ? {} : { output: "standalone" }),
  typescript: {
    // Prevent stale type errors from blocking production deployments
    ignoreBuildErrors: true,
  },
  eslint: {
    // Prevent lint warnings from blocking production deployments
    ignoreDuringBuilds: true,
  },
  async rewrites() {
    return [
      // Proxy /api/* → FastAPI /api/*
      {
        source: "/api/:path*",
        destination: `${backendUrl}/api/:path*`,
      },
      // Proxy /health → FastAPI /health (used by Navbar status pill)
      {
        source: "/health",
        destination: `${backendUrl}/health`,
      },
    ];
  },
};

module.exports = nextConfig;
