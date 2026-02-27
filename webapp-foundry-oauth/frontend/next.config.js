/** @type {import('next').NextConfig} */
const nextConfig = {
  // Rewrites proxy frontend /api/* calls to the FastAPI backend.
  // This avoids CORS issues and hides the backend URL from the browser.
  async rewrites() {
    const backendUrl =
      process.env.BACKEND_URL || "http://localhost:8000";
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/api/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
