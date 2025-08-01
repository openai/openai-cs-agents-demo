/** @type {import('next').NextConfig} */
const nextConfig = {
  devIndicators: false,
  // Proxy /chat requests to the backend server
  async rewrites() {
    return [
      {
        source: "/chat",
        destination: "http://127.0.0.1:8000/chat",
      },
      {
        source: "/agents-config",
        destination: "http://127.0.0.1:8000/agents-config",
      },
      {
        source: "/agents-config/:path*",
        destination: "http://127.0.0.1:8000/agents-config/:path*",
      },
    ];
  },
};

export default nextConfig;
