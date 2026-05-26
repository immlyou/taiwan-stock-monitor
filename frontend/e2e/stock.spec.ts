import { test, expect } from '@playwright/test'

/**
 * 個股查詢與技術分析
 * 用 2330 (台積電) 作為穩定 fixture。
 */

const TSMC = '2330'

test.describe('個股研究', () => {
  test(`/stock/${TSMC} 個股頁可開啟並顯示股號`, async ({ page }) => {
    await page.goto(`/stock/${TSMC}`)
    await expect(page.locator('body')).not.toContainText(/Application error/i)

    // 頁面任一處該帶到 2330 字樣
    await expect(page.getByText(new RegExp(TSMC)).first()).toBeVisible({
      timeout: 20_000,
    })
  })

  test('/technical 技術分析頁面可載入', async ({ page }) => {
    await page.goto('/technical')
    await expect(page.locator('body')).not.toContainText(/Application error/i)
    await expect(page.getByText('台股監控系統').first()).toBeVisible()
  })

  test('/compare 比較分析頁面可載入', async ({ page }) => {
    await page.goto('/compare')
    await expect(page.locator('body')).not.toContainText(/Application error/i)
  })

  test('/chip 籌碼分析頁面可載入', async ({ page }) => {
    await page.goto('/chip')
    await expect(page.locator('body')).not.toContainText(/Application error/i)
  })

  test('/financials 財報分析頁面可載入', async ({ page }) => {
    await page.goto('/financials')
    await expect(page.locator('body')).not.toContainText(/Application error/i)
  })

  test('Header StockSearch 元件存在且可輸入', async ({ page }) => {
    await page.goto('/')

    // StockSearch 元件可能用 input[role=combobox] 或一般 input；用通用選擇器找
    const searchInput = page
      .locator('header input, input[placeholder*="股票" i], input[placeholder*="搜尋" i]')
      .first()

    await expect(searchInput).toBeVisible({ timeout: 10_000 })
    await searchInput.fill('2330')
    await expect(searchInput).toHaveValue('2330')
  })
})
