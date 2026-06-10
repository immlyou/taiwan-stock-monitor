import type { NextConfig } from "next";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

const projectRoot = dirname(fileURLToPath(import.meta.url));

const nextConfig: NextConfig = {
  // 注意：Vercel 部署不需要 output: 'standalone'（Vercel 自行處理輸出格式）
  // 若要自架 Docker，請取消下一行的注解：
  // output: 'standalone',
  images: {
    unoptimized: true,
  },
  turbopack: {
    root: projectRoot,
  },
  // /api/* 的後端轉發改由 src/app/api/[...path]/route.ts 處理
  // （rewrite 無法注入 Authorization header，故移除）
};

export default nextConfig;
