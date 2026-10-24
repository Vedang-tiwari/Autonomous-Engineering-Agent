/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Support standalone output for dockerization
  output: 'standalone',
};

module.exports = nextConfig;
