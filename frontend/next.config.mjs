/** @type {import('next').NextConfig} */
const nextConfig = {
  // Standalone output gives a small self-contained server for the Docker image.
  output: "standalone",
  cacheComponents: true,
  partialPrefetching: true,
};

export default nextConfig;
