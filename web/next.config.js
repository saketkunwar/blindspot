/** @type {import('next').NextConfig} */
const nextConfig = {
  async redirects() {
    return [{ source: "/", destination: "/demos", permanent: false }];
  },
};
module.exports = nextConfig;
