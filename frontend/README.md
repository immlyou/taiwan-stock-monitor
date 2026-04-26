# 台股戰情中心前端

Next.js 前端，提供台股戰情中心的正式 Web UI。後端 API 由根目錄的 FastAPI server 提供。

## 技術棧

- Next.js 16
- React 19
- TypeScript
- Tailwind CSS 4
- SWR
- Radix UI primitives
- lucide-react
- Recharts / lightweight-charts

## 本機開發

先在專案根目錄啟動 API：

```bash
python api_server.py --host 0.0.0.0 --port 8000 --reload
```

再啟動前端：

```bash
cd frontend
npm install
npm run dev
```

開啟 `http://localhost:3000`。

## 環境變數

建立 `frontend/.env.local`：

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

生產環境部署到 Vercel 時，`NEXT_PUBLIC_API_URL` 必須設定為 Railway API：

```env
NEXT_PUBLIC_API_URL=https://taiwan-stock-api-production.up.railway.app
```

## API Proxy

[next.config.ts](./next.config.ts) 會將瀏覽器端 `/api/:path*` rewrite 到 `NEXT_PUBLIC_API_URL`：

```text
/api/market/summary -> https://.../market/summary
```

前端 API helper 位於 [src/lib/api/client.ts](./src/lib/api/client.ts)。Client Components 使用 `/api` proxy；Server Components / SSR 直接使用 `NEXT_PUBLIC_API_URL`。

## 常用指令

```bash
npm run dev
npm run lint
npm run build
npm run start
```

## 部署

部署平台：Vercel。

相關檔案：

- [`vercel.json`](./vercel.json)
- [`next.config.ts`](./next.config.ts)
- 根目錄 [`.vercelignore`](../.vercelignore)

Vercel 建置時只需要前端與少量公開資源。後端程式、測試、FinLab pickle 快取與本機工具資料會由 `.vercelignore` 排除。

## 公開工具目錄

[`public/tool_catalog.json`](./public/tool_catalog.json) 是給外部 AI / app 讀取的工具目錄鏡像，來源應與根目錄 [`openclaw_skill/tool_catalog.json`](../openclaw_skill/tool_catalog.json) 保持一致。
