import type { NextConfig } from "next";
const nextConfig: NextConfig = {
  poweredByHeader: false,
  // Cold offline model identity verification/load is bounded by 180s in backend.
  experimental: { proxyTimeout: 240_000, proxyClientMaxBodySize: 21 * 1024 * 1024 },
  async rewrites() {
    return [{ source: "/api/:path*", destination: "http://127.0.0.1:8000/:path*" }];
  },
};
export default nextConfig;
