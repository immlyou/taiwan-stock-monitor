import type { NextConfig } from "next";
import { readFileSync } from "node:fs";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

const projectRoot = dirname(fileURLToPath(import.meta.url));
const releaseManifest = JSON.parse(
  readFileSync(new URL("../release-manifest.json", import.meta.url), "utf8"),
) as {
  schemaVersion: number;
  productVersion: string;
  frontendVersion: string;
  apiVersion: string;
  releaseDate: string;
};

const nextConfig: NextConfig = {
  // 注意：Vercel 部署不需要 output: 'standalone'（Vercel 自行處理輸出格式）
  // 若要自架 Docker，請取消下一行的注解：
  // output: 'standalone',
  images: {
    unoptimized: true,
  },
  env: {
    NEXT_PUBLIC_RELEASE_SCHEMA_VERSION: String(releaseManifest.schemaVersion),
    NEXT_PUBLIC_PRODUCT_VERSION: releaseManifest.productVersion,
    NEXT_PUBLIC_FRONTEND_VERSION: releaseManifest.frontendVersion,
    NEXT_PUBLIC_API_VERSION: releaseManifest.apiVersion,
    NEXT_PUBLIC_RELEASE_DATE: releaseManifest.releaseDate,
  },
  turbopack: {
    root: projectRoot,
  },
  // /api/* 的後端轉發改由 src/app/api/[...path]/route.ts 處理
  // （rewrite 無法注入 Authorization header，故移除）
};

export default nextConfig;
