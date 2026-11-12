const nextConfig = {
  async rewrites() {
    return process.env.LOCAL_API_PROXY === '1' ? {
      beforeFiles: [{ source: '/api/:path*', destination: 'http://127.0.0.1:8787/api/:path*' }],
    } : [];
  },
  outputFileTracingIncludes: {
    '/api/*': ['./runtime/**/*'],
  },
};

export default nextConfig;
