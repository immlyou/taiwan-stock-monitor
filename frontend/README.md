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
STOCK_API_KEY=與後端相同的_server_only_key
AUTH_SECRET=至少_32_字元的隨機值
AUTH_GOOGLE_ID=Google_OAuth_Client_ID
AUTH_GOOGLE_SECRET=Google_OAuth_Client_Secret
AUTH_ALLOWED_EMAIL=imchris.yu@gmail.com
```

生產環境部署到 Vercel 時，`NEXT_PUBLIC_API_URL` 必須設定為 Railway API：

```env
NEXT_PUBLIC_API_URL=https://taiwan-stock-api-production.up.railway.app
```

Google OAuth redirect URI：

```text
http://localhost:3000/api/auth/callback/google
https://taiwan-stock-monitor.vercel.app/api/auth/callback/google
```

`AUTH_SECRET` 可用 `npx auth secret` 產生。`AUTH_ALLOWED_EMAIL` 採不分大小寫的
完整信箱比對，未設定時會 fail closed、拒絕所有帳號。`STOCK_API_KEY`、
`AUTH_GOOGLE_SECRET` 與 `AUTH_SECRET` 都不可加 `NEXT_PUBLIC_` 前綴。
既有 `data/*.json` 的站長資料要接到 Google 帳號時，登入後從
`/api/auth/session` 複製 `user.id`，並在 Railway 設定同值的
`DEFAULT_USER_ID`。

## Google OAuth 與 API Proxy

[src/proxy.ts](./src/proxy.ts) 保護頁面；
[src/app/api/[...path]/route.ts](./src/app/api/[...path]/route.ts) 只接受已驗證的
Google session，再將 `/api/:path*` 代理到 `NEXT_PUBLIC_API_URL`：

```text
/api/market/summary -> https://.../market/summary
```

Route Handler 會覆寫 `X-User-ID`，並由 server 注入 `STOCK_API_KEY`；瀏覽器無法
指定別人的資料 namespace。前端 API helper 位於
[src/lib/api/client.ts](./src/lib/api/client.ts)。

## 常用指令

```bash
npm run dev
npm run lint
npm run test:unit
npm run build
npm run start
npm run test:e2e:smoke
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
