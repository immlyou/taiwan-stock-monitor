import { encode } from '@auth/core/jwt'
import { test, expect, type BrowserContext } from '@playwright/test'

async function signIn(context: BrowserContext, baseURL: string, userId: string, email?: string) {
  const name = 'authjs.session-token'
  const value = await encode({
    salt: name, secret: 'contract-only-secret-contract-only-secret',
    token: { sub: userId, userId, email: email ?? (userId === 'google_contract_alice' ? 'contract@example.test' : `${userId.replace('google_contract_', '')}@example.test`), name: 'Contract User' },
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

test('real model API discloses heuristic scores, EWMA fallback and legacy evidence', async ({ page, context, baseURL }) => {
  await signIn(context, baseURL!, 'google_contract_alice')
  const ranking = await context.request.get(`${baseURL}/api/strategy/ai-xgboost?top_n=5`, { timeout: 65000 })
  expect(ranking.ok()).toBeTruthy()
  const data = await ranking.json()
  expect(data.score_kind).toBe('heuristic_not_probability')
  expect(data.validation_status).toBe('not_validated_for_investment')
  expect(data.stocks).toHaveLength(5)
  expect(data.stocks[0].model_version).toContain('xgb-2')
  const trend = await (await context.request.get(`${baseURL}/api/strategy/ai-lstm/2330`)).json()
  expect(trend.model_used).toBe('ewma')
  expect(trend.experimental).toBe(true)
  expect(trend.score_kind).toBe('heuristic_not_probability')
  const study = await (await context.request.get(`${baseURL}/api/strategy/ai-xgboost/backtest`)).json()
  expect(study.current_model_comparable).toBe(false)
  expect(study.status).toBe('legacy_not_comparable')
  await page.goto('/ai-pick')
  await expect(page.getByText('contract@example.test', { exact: true })).toBeVisible()
  await expect(page.getByRole('columnheader', { name: '排序分數' })).toBeVisible()
  await expect(page.getByText('不是上漲機率或勝率', { exact: false })).toBeVisible()
  const ledger = page.getByRole('region', { name: 'XGBoost 交易生命週期研究' })
  await expect(ledger.getByText('24 / 24', { exact: true })).toBeVisible()
  await expect(ledger.getByText('23 / 24', { exact: true })).toBeVisible()
  await expect(ledger.getByText('9 / 24', { exact: true })).toBeVisible()
  await ledger.locator('summary').filter({ hasText: '2026-03-30' }).click()
  await expect(ledger.getByText('停牌未平倉', { exact: false })).toBeVisible()
  await page.getByRole('button', { name: 'LSTM 趨勢', exact: true }).click()
  await expect(page.getByText('輸入股票代號以查詢 LSTM 趨勢預測', { exact: true })).toBeVisible()
  await page.getByRole('main').getByRole('combobox', { name: '搜尋股票' }).fill('2330')
  await page.getByRole('option', { name: /2330.*台積電/ }).click()
  await expect(page.getByText('EWMA 趨勢推估（非 LSTM）', { exact: false })).toBeVisible()
})

test('account management UI and live role/disable enforcement through the real proxy', async ({ page, context, browser, baseURL }) => {
  await signIn(context, baseURL!, 'google_contract_alice')
  await page.goto('/admin/accounts')
  await expect(page.getByRole('heading', { name: '帳號管理', exact: true })).toBeVisible()
  await expect(page.getByLabel('contract@example.test 啟用')).toBeDisabled()
  await page.getByLabel('Google Email', { exact: true }).fill('viewer@example.test')
  await page.getByLabel('邀請角色').selectOption('viewer')
  await page.getByRole('button', { name: '加入帳號' }).click()
  await expect(page.getByText('已邀請，待登入', { exact: true })).toBeVisible()

  const api = `http://127.0.0.1:${process.env.PLAYWRIGHT_API_PORT ?? 41738}`
  const registered = await context.request.post(`${api}/internal/accounts/google-login`, {
    headers: { authorization: 'Bearer contract-only-api-key' },
    data: { user_id: 'google_contract_viewer', email: 'viewer@example.test', name: 'Viewer' },
  })
  expect(registered.status()).toBe(200)
  const viewer = await browser.newContext()
  try {
    await signIn(viewer, baseURL!, 'google_contract_viewer', 'viewer@example.test')
    expect((await viewer.request.get(`${baseURL}/api/admin/accounts`)).status()).toBe(403)
    expect((await viewer.request.get(`${baseURL}/api/settings`)).status()).toBe(200)
    expect((await viewer.request.put(`${baseURL}/api/settings`, { data: { system: { dataUpdateInterval: 60 } } })).status()).toBe(403)
    expect((await viewer.request.post(`${baseURL}/api/internal/accounts/google-login`, { data: {
      user_id: 'google_contract_viewer', email: 'viewer@example.test', bootstrap_email: 'viewer@example.test',
    } })).status()).toBe(403)
    const viewerPage = await viewer.newPage()
    await viewerPage.goto('/admin/accounts')
    await expect(viewerPage.getByText('此頁面僅開放管理員使用。')).toBeVisible()
    await expect(viewerPage.getByRole('link', { name: '帳號管理', exact: true })).toHaveCount(0)

    page.on('dialog', (dialog) => dialog.accept())
    await page.getByLabel('viewer@example.test 權限').selectOption('member')
    const row = page.getByRole('row').filter({ has: page.getByLabel('viewer@example.test 權限') })
    await row.getByRole('button', { name: '儲存' }).click()
    await expect.poll(async () => (await (await viewer.request.get(`${baseURL}/api/accounts/me`)).json()).role).toBe('member')
    expect((await viewer.request.put(`${baseURL}/api/settings`, { data: { system: { dataUpdateInterval: 60 } } })).status()).toBe(200)
    await page.getByLabel('viewer@example.test 啟用').uncheck()
    await row.getByRole('button', { name: '儲存' }).click()
    await expect.poll(async () => (await viewer.request.get(`${baseURL}/api/settings`)).status()).toBe(403)
    const relogin = await context.request.post(`${api}/internal/accounts/google-login`, {
      headers: { authorization: 'Bearer contract-only-api-key' },
      data: { user_id: 'google_contract_viewer', email: 'viewer@example.test' },
    })
    expect(relogin.status()).toBe(403)
  } finally { await viewer.close() }
})
