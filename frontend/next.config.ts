import type { NextConfig } from "next";

/** @type {import('next').NextConfig} */
const nextConfig: NextConfig = {
  // ---------------------------------------------------------------------------
  // Experimental features
  // ---------------------------------------------------------------------------
  experimental: {
    // Enable React Server Components (default in App Router)
    serverComponentsExternalPackages: [],
  },

  // ---------------------------------------------------------------------------
  // Environment variables exposed to the browser
  // ---------------------------------------------------------------------------
  env: {
    NEXT_PUBLIC_APP_VERSION: process.env.npm_package_version ?? "1.0.0",
  },

  // ---------------------------------------------------------------------------
  // Image optimization
  // ---------------------------------------------------------------------------
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "avatars.githubusercontent.com",
      },
      {
        protocol: "https",
        hostname: "*.vercel.app",
      },
    ],
    formats: ["image/avif", "image/webp"],
  },

  // ---------------------------------------------------------------------------
  // Security headers
  // ---------------------------------------------------------------------------
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          {
            key: "X-Frame-Options",
            value: "DENY",
          },
          {
            key: "X-Content-Type-Options",
            value: "nosniff",
          },
          {
            key: "Referrer-Policy",
            value: "strict-origin-when-cross-origin",
          },
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=()",
          },
          {
            key: "X-XSS-Protection",
            value: "1; mode=block",
          },
        ],
      },
    ];
  },

  // ---------------------------------------------------------------------------
  // Redirects
  // ---------------------------------------------------------------------------
  async redirects() {
    return [
      // Redirect root to dashboard for authenticated users
      // (actual auth check is handled by middleware.ts)
      {
        source: "/",
        destination: "/dashboard",
        permanent: false,
      },
    ];
  },

  // ---------------------------------------------------------------------------
  // Rewrites (API proxy for local dev to avoid CORS)
  // ---------------------------------------------------------------------------
  async rewrites() {
    return process.env.NODE_ENV === "development"
      ? [
          {
            source: "/api/backend/:path*",
            destination: `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/:path*`,
          },
        ]
      : [];
  },

  // ---------------------------------------------------------------------------
  // TypeScript + ESLint
  // ---------------------------------------------------------------------------
  typescript: {
    // In production builds, fail if there are type errors
    ignoreBuildErrors: false,
  },
  eslint: {
    ignoreDuringBuilds: false,
  },

  // ---------------------------------------------------------------------------
  // Output configuration
  // ---------------------------------------------------------------------------
  output: "standalone", // Required for Docker deployment
  poweredByHeader: false, // Remove X-Powered-By header
  compress: true,

  // ---------------------------------------------------------------------------
  // Logging
  // ---------------------------------------------------------------------------
  logging: {
    fetches: {
      fullUrl: process.env.NODE_ENV === "development",
    },
  },
};

export default nextConfig;
