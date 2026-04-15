import type { NextConfig } from "next";
import path from "node:path";

const nextConfig: NextConfig = {
  // Pin Turbopack workspace root so it doesn't climb to ~/ on lockfile detection.
  turbopack: {
    root: path.resolve(__dirname),
  },
};

export default nextConfig;
