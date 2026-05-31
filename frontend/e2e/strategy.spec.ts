import { test, expect } from '@playwright/test'

/**
 * 策略 / 選股 / 回測
 * 這些頁面通常會打 API；先驗頁面結構，再儘量驗主要表單/按鈕存在。
 */

test.describe('選股策略', () => {
  test('/screener 選股篩選頁面可載入', async ({ page }) => {
    await page.goto('/screener')
    await expect(page.locator('body')).not.toContainText(/Application error/i)
    await expect(page.getByText('台股監控系統').first()).toBeVisible()
  })

  test('/strategies 策略管理頁面可載入', async ({ page }) => {
    await page.goto('/strategies')
    await expect(page.locator('body')).not.toContainText(/Application error/i)
  })

  test('/backtest 回測分析頁面可載入', async ({ page }) => {
    await page.goto('/backtest')
    await expect(page.locator('body')).not.toContainText(/Application error/i)
    await expect(page.getByText('台股監控系統').first()).toBeVisible()
  })

  test('/optimizer 參數優化頁面可載入', async ({ page }) => {
    await page.goto('/optimizer')
    await expect(page.locator('body')).not.toContainText(/Application error/i)
  })

  test('/ai-pick AI 智慧選股頁面可載入', async ({ page }) => {
    await page.goto('/ai-pick')
    await expect(page.locator('body')).not.toContainText(/Application error/i)
  })

  test('/trading-radar AI 操盤雷達頁面可載入', async ({ page }) => {
    await page.goto('/trading-radar')
    await expect(page.locator('body')).not.toContainText(/Application error/i)
  })

  test('/ai-anomaly AI 異常警報頁面可載入', async ({ page }) => {
    await page.goto('/ai-anomaly')
    await expect(page.locator('body')).not.toContainText(/Application error/i)
  })

  test('/predictions 預測驗證頁面可載入', async ({ page }) => {
    await page.goto('/predictions')
    await expect(page.locator('body')).not.toContainText(/Application error/i)
  })

  test('/hidden-gems 遺珠掃描頁面可載入', async ({ page }) => {
    await page.goto('/hidden-gems')
    await expect(page.locator('body')).not.toContainText(/Application error/i)
  })
})
