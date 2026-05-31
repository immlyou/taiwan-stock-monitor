import { test, expect } from '@playwright/test'

/**
 * Smoke：首頁可開、主要導航群組與分頁路徑可達。
 * 目標：抓「能不能載入」這層的崩潰，不驗資料正確性。
 */

test.describe('首頁與導覽', () => {
  test('首頁載入成功，標題與市場戰情中心區段存在', async ({ page }) => {
    await page.goto('/')

    await expect(page).toHaveTitle(/台股監控系統/)
    await expect(
      page.getByRole('heading', { name: '市場戰情中心' })
    ).toBeVisible()

    // sidebar logo
    await expect(page.getByText('台股監控系統')).toBeVisible()
  })

  test('側邊欄包含四個主要導覽群組', async ({ page }) => {
    await page.goto('/')

    for (const label of ['市場動態', '研究分析', '選股策略', '投資管理']) {
      await expect(page.getByRole('button', { name: new RegExp(label) })).toBeVisible()
    }
  })

  const ROUTES: Array<{ path: string; heading?: RegExp }> = [
    { path: '/dashboard' },
    { path: '/realtime' },
    { path: '/heatmap' },
    { path: '/money-flow' },
    { path: '/after-hours' },
    { path: '/morning-report' },
    { path: '/technical' },
    { path: '/compare' },
    { path: '/industry' },
    { path: '/chip' },
    { path: '/financials' },
    { path: '/risk' },
    { path: '/screener' },
    { path: '/ai-pick' },
    { path: '/trading-radar' },
    { path: '/backtest' },
    { path: '/strategies' },
    { path: '/optimizer' },
    { path: '/predictions' },
    { path: '/hidden-gems' },
    { path: '/portfolio' },
    { path: '/watchlist' },
    { path: '/journal' },
    { path: '/alerts' },
    { path: '/settings' },
  ]

  for (const { path } of ROUTES) {
    test(`路由可達：${path}`, async ({ page }) => {
      const consoleErrors: string[] = []
      page.on('pageerror', (err) => consoleErrors.push(String(err)))

      const resp = await page.goto(path, { waitUntil: 'domcontentloaded' })
      expect(resp?.status(), `${path} HTTP status`).toBeLessThan(400)

      // 至少要有 sidebar logo 代表 RootLayout 成功 mount
      await expect(page.getByText('台股監控系統').first()).toBeVisible()
      expect(consoleErrors, `${path} 不應拋出未捕獲例外`).toEqual([])
    })
  }
})
