/** @type {import('next').NextConfig} */
const backendUrl = process.env.BACKEND_INTERNAL_URL ?? "http://127.0.0.1:8000";

const nextConfig = {
  devIndicators: false,
  // Proxy /chat requests to the backend server
  async rewrites() {
    return [
      {
        source: "/chat",
        destination: `${backendUrl}/chat`,
      },
      {
        source: "/chatkit",
        destination: `${backendUrl}/chatkit`,
      },
      {
        source: "/chatkit/:path*",
        destination: `${backendUrl}/chatkit/:path*`,
      },
      {
        source: "/v1/:path*",
        destination: `${backendUrl}/v1/:path*`,
      },
      {
        source: "/auth/:path*",
        destination: `${backendUrl}/auth/:path*`,
      },
    ];
  },
};

export default nextConfig;
