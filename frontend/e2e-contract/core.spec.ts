import { encode } from '@auth/core/jwt'
import { test, expect, type BrowserContext } from '@playwright/test'

async function signIn(context: BrowserContext, baseURL: string, userId: string) {
  const name = 'authjs.session-token'
  const value = await encode({
    salt: name, secret: 'contract-only-secret-contract-only-secret',
    token: { sub: userId, userId, email: 'contract@example.test', name: 'Contract User' },
  })
  await context.addCookies([{ name, value, url: baseURL, httpOnly: true, sameSite: 'Lax' }])
}

test('real proxy/API prediction CRUD and identity isolation', async ({ page, context, browser, baseURL }) => {
  await signIn(context, baseURL!, 'google_contract_alice')
  await page.goto('/predictions')
  await page.getByRole('button', { name: '新增預測', exact: true }).click()
  await page.getByLabel('股票代號').fill('2330')
  await page.getByLabel('目標價', { exact: true }).fill('120')
  const future = new Date(Date.now() + 7 * 86400000).toISOString().slice(0, 10)
  await page.getByLabel('目標日期').fill(future)
  await page.getByRole('button', { name: '新增', exact: true }).click()
  await expect(page.getByRole('cell', { name: '2330', exact: true })).toBeVisible()
  const listed = await (await context.request.get(`${baseURL}/api/predictions`)).json()
  expect(listed.predictions[0].targetPrice).toBe(120)

  const bob = await browser.newContext()
  try {
    await signIn(bob, baseURL!, 'google_contract_bob')
    const records = await (await bob.request.get(`${baseURL}/api/predictions`, {
      headers: { 'x-user-id': 'google_contract_alice' },
    })).json()
    expect(records.total).toBe(0)
    expect((await bob.request.delete(`${baseURL}/api/predictions/${listed.predictions[0].id}`)).status()).toBe(404)
  } finally {
    await bob.close()
  }

  await page.getByRole('button', { name: '刪除', exact: true }).click()
  await page.getByRole('button', { name: '刪除', exact: true }).last().click()
  await expect(page.getByText('尚無預測記錄，點擊新增預測開始追蹤')).toBeVisible()
})

test('settings UI persists effective settings and never receives saved secrets', async ({ page, context, baseURL }) => {
  await signIn(context, baseURL!, 'google_contract_settings')
  const saved = await context.request.put(`${baseURL}/api/settings`, { data: {
    telegram: { enabled: true, botToken: 'test-only-secret', chatId: 'test-chat' },
  } })
  expect(saved.ok()).toBeTruthy()
  await page.goto('/settings')
  await page.getByLabel('行情報價最短更新間隔').fill('90')
  await page.getByRole('button', { name: '儲存設定' }).click()
  await expect.poll(async () => (await (await context.request.get(`${baseURL}/api/settings`)).json()).system.dataUpdateInterval).toBe(90)
  const response = await context.request.get(`${baseURL}/api/settings`)
  expect(await response.text()).not.toContain('test-only-secret')
  expect((await response.json()).telegram.botTokenConfigured).toBe(true)
  await expect(page.getByRole('switch', { name: '自動定期回測' })).toBeDisabled()
})

test('unauthenticated proxy access stays rejected', async ({ request, baseURL }) => {
  const response = await request.get(`${baseURL}/api/predictions`)
  expect(response.status()).toBe(401)
})
