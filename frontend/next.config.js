/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  reactStrictMode: true,
  turbopack: {
    root: __dirname,
  },
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'images.unsplash.com',
      },
      {
        protocol: 'https',
        hostname: 'assets-in.bmscdn.com',
      },
      {
        protocol: 'https',
        hostname: 'in.bmscdn.com',
      },
      {
        protocol: 'https',
        hostname: 'media-assets.swiggy.com',
      },
      {
        protocol: 'https',
        hostname: 'res.cloudinary.com',
      },
    ],
  },
  async rewrites() {
    const internalBackendUrl =
      process.env.INTERNAL_API_URL ||
      process.env.NEXT_PUBLIC_API_URL ||
      'http://127.0.0.1:8000';
    return [
      {
        source: '/api/:path*',
        destination: `${internalBackendUrl}/api/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
