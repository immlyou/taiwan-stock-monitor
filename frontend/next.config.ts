import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // 注意：Vercel 部署不需要 output: 'standalone'（Vercel 自行處理輸出格式）
  // 若要自架 Docker，請取消下一行的注解：
  // output: 'standalone',
  images: {
    unoptimized: true,
  },
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/:path*`,
      },
    ];
  },
};

export default nextConfig;
