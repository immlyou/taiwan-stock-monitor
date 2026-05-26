import { test, expect } from '@playwright/test'

/**
 * 市場總覽 / 熱力圖 / 大盤
 * 驗 UI 結構出現、不爆，且關鍵資料區塊有渲染（資料本身的正確性留給 API 測試）。
 */

test.describe('市場動態', () => {
  test('首頁市場戰情中心至少渲染一個資料卡片', async ({ page }) => {
    await page.goto('/')

    await expect(
      page.getByRole('heading', { name: '市場戰情中心' })
    ).toBeVisible()

    // MarketDashboard 渲染後，主內容區應有實際文字（避免空白頁面）
    const main = page.getByRole('main')
    await expect(main).toBeVisible()
    await expect(main).not.toBeEmpty()
  })

  test('/dashboard 持倉總覽可開啟', async ({ page }) => {
    await page.goto('/dashboard')
    // sidebar item 是「持倉總覽」，但實際頁面 heading 可能不同
    // 用較鬆的斷言：頁面有渲染且沒有 Error Boundary 文字
    await expect(page.locator('body')).not.toContainText(/Application error/i)
    await expect(page.locator('body')).not.toContainText(/something went wrong/i)
  })

  test('/heatmap 熱力圖頁面結構正常', async ({ page }) => {
    await page.goto('/heatmap')
    await expect(page.locator('body')).not.toContainText(/Application error/i)
    // sidebar logo 仍要在（layout 沒崩）
    await expect(page.getByText('台股監控系統').first()).toBeVisible()
  })

  test('/realtime 即時報價頁面可載入', async ({ page }) => {
    await page.goto('/realtime')
    await expect(page.locator('body')).not.toContainText(/Application error/i)
    await expect(page.getByText('台股監控系統').first()).toBeVisible()
  })

  test('/money-flow 資金流向頁面可載入', async ({ page }) => {
    await page.goto('/money-flow')
    await expect(page.locator('body')).not.toContainText(/Application error/i)
  })

  test('/after-hours 盤後總覽頁面可載入', async ({ page }) => {
    await page.goto('/after-hours')
    await expect(page.locator('body')).not.toContainText(/Application error/i)
  })
})
