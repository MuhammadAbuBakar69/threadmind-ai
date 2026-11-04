import type { NextConfig } from "next";

const config: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  images: {
    // Fabric imagery is served from object storage via short-lived signed URLs.
    remotePatterns: [{ protocol: "https", hostname: "**" }],
  },
};

export default config;
