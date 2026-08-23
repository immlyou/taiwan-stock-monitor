import { test, expect } from '@playwright/test'

test.describe('Google OAuth access boundary', () => {
  test('protected home redirects to the Google sign-in page', async ({ page }) => {
    await page.goto('/')

    await expect(page).toHaveURL(/\/login(?:\?|$)/)
    await expect(page).toHaveTitle(/台股監控系統/)
    await expect(page.getByRole('heading', { name: '登入你的投研工作台' })).toBeVisible()
    await expect(page.getByRole('button', { name: '使用 Google 登入' })).toBeVisible()
  })

  test('protected settings route cannot bypass login', async ({ page }) => {
    await page.goto('/settings')

    await expect(page).toHaveURL(/\/login(?:\?|$)/)
    await expect(page.getByRole('button', { name: '使用 Google 登入' })).toBeVisible()
  })

  test('backend proxy returns 401 without a verified session', async ({ request }) => {
    const response = await request.get('/api/settings')

    expect(response.status()).toBe(401)
    await expect(response.json()).resolves.toEqual({ error: 'authentication_required' })
  })
})
