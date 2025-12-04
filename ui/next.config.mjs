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
        source: "/chatkit",
        destination: "http://127.0.0.1:8000/chatkit",
      },
      {
        source: "/chatkit/:path*",
        destination: "http://127.0.0.1:8000/chatkit/:path*",
      },
    ];
  },
};

export default nextConfig;
