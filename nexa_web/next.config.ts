import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  // v2.1.0: TypeScript errors must surface at build time (was ignored before).
  typescript: { ignoreBuildErrors: false },
  reactStrictMode: false,
  async rewrites() {
    return [
      { source: "/api/:path*", destination: "http://127.0.0.1:8000/api/:path*" },
    ];
  },
};

export default nextConfig;
