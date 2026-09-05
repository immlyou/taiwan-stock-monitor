import { defineConfig, devices } from '@playwright/test'

/**
 * Playwright E2E 設定
 *
 * 預設啟動本機 Next.js；需要驗證外部部署時可用 PLAYWRIGHT_BASE_URL 覆寫。
 */
const EXTERNAL_BASE_URL = process.env.PLAYWRIGHT_BASE_URL
const LOCAL_PORT = process.env.PLAYWRIGHT_PORT ?? '3000'
const BASE_URL = EXTERNAL_BASE_URL ?? `http://localhost:${LOCAL_PORT}`

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 1,
  workers: process.env.CI ? 2 : undefined,
  reporter: [['list'], ['html', { open: 'never' }]],
  timeout: 60_000,
  expect: { timeout: 15_000 },
  webServer: EXTERNAL_BASE_URL
    ? undefined
    : {
        command: `npm run dev -- --port ${LOCAL_PORT}`,
        url: BASE_URL,
        reuseExistingServer: !process.env.CI,
        timeout: 120_000,
      },
  use: {
    baseURL: BASE_URL,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    navigationTimeout: 30_000,
    actionTimeout: 15_000,
    locale: 'zh-TW',
    timezoneId: 'Asia/Taipei',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
})
