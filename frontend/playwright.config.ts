import { defineConfig, devices } from '@playwright/test'

/**
 * Playwright E2E 設定
 *
 * 預設打到 Vercel 線上正式環境；可用 PLAYWRIGHT_BASE_URL 覆寫，例如：
 *   PLAYWRIGHT_BASE_URL=http://localhost:3000 npx playwright test
 */
const BASE_URL =
  process.env.PLAYWRIGHT_BASE_URL ?? 'https://taiwan-stock-monitor.vercel.app'

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 1,
  workers: process.env.CI ? 2 : undefined,
  reporter: [['list'], ['html', { open: 'never' }]],
  timeout: 60_000,
  expect: { timeout: 15_000 },
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
