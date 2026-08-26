import { encode } from '@auth/core/jwt'
import { expect, test, type BrowserContext, type Page } from '@playwright/test'

const AUTH_COOKIE = 'authjs.session-token'
const AUTH_SECRET = process.env.AUTH_SECRET ?? 'ci-only-secret-ci-only-secret-1234'
const AUTH_EMAIL = process.env.AUTH_ALLOWED_EMAIL ?? 'imchris.yu@gmail.com'

// These tests intentionally exercise several lazily compiled app routes. Keep
// them serial so the local Next.js server is not overwhelmed by route builds.
test.describe.configure({ mode: 'serial' })
test.setTimeout(120_000)

async function signInAsAllowedGoogleUser(
  context: BrowserContext,
  baseURL: string,
  userId = 'google_e2e_google_account'
) {
  const token = await encode({
    salt: AUTH_COOKIE,
    secret: AUTH_SECRET,
    token: {
      sub: 'e2e-google-account',
      userId,
      email: AUTH_EMAIL,
      name: 'E2E Owner',
    },
  })
  await context.addCookies([
    {
      name: AUTH_COOKIE,
      value: token,
      url: baseURL,
      httpOnly: true,
      sameSite: 'Lax',
      secure: baseURL.startsWith('https://'),
    },
  ])
}

async function mockUnavailableAppApi(page: Page) {
  await page.route('**/api/**', async (route) => {
    if (new URL(route.request().url()).pathname.startsWith('/api/auth/')) {
      await route.continue()
      return
    }
    await route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'fixture unavailable' }),
    })
  })
}

test.beforeEach(async ({ context, baseURL }) => {
  await signInAsAllowedGoogleUser(context, baseURL ?? 'http://localhost:3000')
})

test('authenticated owner can reach protected core features', async ({ page }) => {
  await mockUnavailableAppApi(page)

  const routes = [
    ['/', '市場戰情中心'],
    ['/portfolio', '投資組合'],
    ['/watchlist', '自選股'],
    ['/alerts', 'Alerts 2.0'],
    ['/settings', '系統設定'],
    ['/trading-radar', 'AI 操盤雷達'],
  ] as const

  for (const [path, heading] of routes) {
    await page.goto(path, { waitUntil: 'domcontentloaded', timeout: 60_000 })
    await expect(page).not.toHaveURL(/\/login(?:\?|$)/)
    await expect(page.getByRole('heading', { name: heading })).toBeVisible()
    if (path === '/portfolio') {
      await expect(page.getByText('投資組合載入失敗')).toBeVisible()
    }
    if (path === '/watchlist') {
      await expect(page.getByText('自選股載入失敗')).toBeVisible()
    }
  }
})

test('settings exposes a retry action when its API is unavailable', async ({ page }) => {
  await page.route('**/api/**', async (route) => {
    if (new URL(route.request().url()).pathname.startsWith('/api/auth/')) {
      return route.continue()
    }
    return route.fulfill({
      status: 503,
      json: { detail: 'settings fixture unavailable' },
    })
  })

  await page.goto('/settings')
  await expect(page.getByText('設定載入失敗')).toBeVisible()
  await expect(page.getByRole('button', { name: '重新載入' })).toBeVisible()
})

test('settings shows the complete version history through the current release', async ({ page }) => {
  await page.route('**/api/**', async (route) => {
    const pathname = new URL(route.request().url()).pathname
    if (pathname.startsWith('/api/auth/')) return route.continue()
    if (pathname === '/api/settings') {
      return route.fulfill({
        json: {
          theme: 'light', language: 'zh-TW', notifications_enabled: true, default_days: 60,
          telegram: { enabled: false, chatId: '', botTokenConfigured: false },
          email: {
            enabled: false, smtpHost: 'smtp.gmail.com', smtpPort: 587,
            username: '', recipient: '', passwordConfigured: false,
          },
          system: {
            dataUpdateInterval: 30, timezone: 'Asia/Taipei', autoBacktest: false,
            marketOpenTime: '09:00', marketCloseTime: '13:30',
          },
        },
      })
    }
    if (pathname === '/api/system/info') {
      return route.fulfill({
        json: {
          version: '5.1.1', apiVersion: '5.1.1', uptime: '1 分',
          dataLastUpdated: '2026-08-26', stockCount: 2300, dbSize: '1.0 GB',
        },
      })
    }
    return route.fulfill({ status: 404, json: { detail: 'missing fixture' } })
  })

  await page.goto('/settings')

  await expect(page.getByRole('heading', { name: '版本記錄' })).toBeVisible()
  await expect(page.getByText('v5.1.1', { exact: true })).toHaveCount(2)
  await expect(page.getByText('v0.1.0', { exact: true })).toHaveCount(1)
  await expect(page.getByText(/Google OAuth/).first()).toBeVisible()
  await expect(page.getByText(/Fugle \/ TWSE/).first()).toBeVisible()
  await expect(page.getByText(/single-flight/).first()).toBeVisible()
})

test('stock detail reports a critical API failure', async ({ page }) => {
  await mockUnavailableAppApi(page)

  await page.goto('/stock/2330', { waitUntil: 'domcontentloaded', timeout: 60_000 })
  await expect(page.getByText('個股資料載入失敗')).toBeVisible()
  await expect(page.getByRole('button', { name: '重新載入' })).toBeVisible()
})

test('realtime page identifies a Fugle live quote', async ({ page }) => {
  await page.route('**/api/**', async (route) => {
    const pathname = new URL(route.request().url()).pathname
    if (pathname.startsWith('/api/auth/')) return route.continue()
    if (pathname === '/api/watchlists/default') {
      return route.fulfill({
        json: {
          id: 'default', name: 'default', stocks_count: 1,
          stocks: [{ stock_id: '2330' }],
        },
      })
    }
    if (pathname === '/api/quote/realtime/batch') {
      return route.fulfill({
        json: {
          total: 1,
          requested: 1,
          date: '2026-08-24',
          market_state: 'trading',
          has_realtime: true,
          sources: ['fugle'],
          quotes: [{
            stock_id: '2330', name: '台積電', price: 123.5,
            change_pct: 2.92, volume: 5000, amount: 605000,
            date: '2026-08-24', timestamp: '2026-08-24T10:00:01+08:00',
            source: 'fugle', is_realtime: true,
            market_state: 'trading', freshness: 'realtime',
          }],
        },
      })
    }
    if (pathname === '/api/market/summary') {
      return route.fulfill({
        json: { taiex_index: 25000, taiex_change: 100 },
      })
    }
    return route.fulfill({ status: 404, json: { detail: 'missing fixture' } })
  })

  await page.goto('/realtime')

  await expect(page.getByRole('heading', { name: '即時報價' })).toBeVisible()
  await expect(page.getByRole('main').getByText('台積電')).toBeVisible()
  await expect(page.getByRole('main').getByText('即時 · Fugle')).toBeVisible()
})

test('XGBoost keeps the last result when a refresh temporarily fails', async ({ page }) => {
  let unavailable = false
  let delaySuccess = false
  let stockName = '快取中的模型結果'

  await page.route('**/api/**', async (route) => {
    const pathname = new URL(route.request().url()).pathname
    if (pathname.startsWith('/api/auth/')) return route.continue()
    if (pathname === '/api/market/summary') {
      return route.fulfill({
        json: { taiex_index: 25000, taiex_change: 100 },
      })
    }
    if (pathname === '/api/strategy/ai-xgboost') {
      if (unavailable) {
        return route.fulfill({
          status: 503,
          json: { detail: 'upstream temporarily unavailable' },
        })
      }
      if (delaySuccess) {
        await new Promise((resolve) => setTimeout(resolve, 750))
      }
      return route.fulfill({
        json: {
          stocks: [{
            stock_id: '2330',
            name: stockName,
            price: 100,
            predicted_return: 0.05,
            confidence: 0.8,
            factors: {},
          }],
          feature_importance: { ret20: 0.5 },
        },
      })
    }
    return route.fulfill({ status: 404, json: { detail: 'missing fixture' } })
  })

  await page.goto('/ai-pick')
  // Wait until SessionProvider has switched SWR to the final account-scoped
  // cache; data fetched by the hydration cache is intentionally discarded.
  await expect(page.getByText(AUTH_EMAIL)).toBeVisible({ timeout: 60_000 })
  await expect(page.getByRole('main').getByText('快取中的模型結果')).toBeVisible()

  await page.evaluate(() => window.dispatchEvent(new Event('beforeunload')))
  unavailable = true
  await page.reload()

  await expect(page.getByRole('main').getByText('快取中的模型結果')).toBeVisible()
  await expect(page.getByRole('status')).toContainText('模型服務暫時不可用')
  await expect(page.getByRole('button', { name: '重新嘗試 XGBoost' })).toBeVisible()
  await expect(page.getByText('XGBoost 模型尚未安裝')).toHaveCount(0)

  unavailable = false
  delaySuccess = true
  stockName = '重新整理後的模型結果'
  await page.getByRole('button', { name: '重新嘗試 XGBoost' }).click()
  await expect(page.getByRole('button', { name: '正在重新運算…' })).toBeVisible()
  await expect(page.getByRole('main').getByText('重新整理後的模型結果')).toBeVisible()
})

test('new account can add its first portfolio holding', async ({ page }) => {
  let holdings: Array<{ stock_id: string; shares: number; cost_price: number }> = []

  await page.route('**/api/**', async (route) => {
    const request = route.request()
    const pathname = new URL(request.url()).pathname
    if (pathname.startsWith('/api/auth/')) return route.continue()
    if (pathname === '/api/portfolios/default/diagnostics') {
      return route.fulfill({
        json: {
          portfolio_id: 'default',
          holdings_count: holdings.length,
          total_value: 0,
          concentration: { top_holding_weight: 0, top_industry_weight: 0 },
          allocation: [],
          risk: { annualized_volatility_pct: 0, max_drawdown_pct: 0 },
          suggestions: [],
        },
      })
    }
    if (pathname === '/api/portfolios/default' && request.method() === 'PUT') {
      holdings = request.postDataJSON().holdings
      return route.fulfill({ json: { message: '更新成功', id: 'default' } })
    }
    if (pathname === '/api/portfolios/default') {
      return route.fulfill({
        json: {
          id: 'default',
          name: 'default',
          description: '',
          created_at: '',
          holdings: holdings.map((holding) => ({
            ...holding,
            name: holding.stock_id === '2330' ? '台積電' : holding.stock_id,
            current_price: holding.cost_price,
            current_value: holding.shares * holding.cost_price,
            pnl: 0,
            pnl_pct: 0,
            price_history: [],
          })),
          summary: {
            total_cost: 0,
            total_value: 0,
            total_pnl: 0,
            total_pnl_pct: 0,
          },
        },
      })
    }
    return route.fulfill({ status: 404, json: { detail: 'missing fixture' } })
  })

  await page.goto('/portfolio')
  // Session resolution changes the SWR provider from the hydration cache to
  // the final account-scoped cache. Wait for that boundary before opening a
  // stateful dialog so the test exercises the settled authenticated UI.
  await expect(page.getByText(AUTH_EMAIL)).toBeVisible({ timeout: 60_000 })
  await page.getByRole('button', { name: '新增持股' }).click()
  await page.getByPlaceholder('例：2330').fill('2330')
  await page.getByPlaceholder('例：10').fill('1')
  await page.getByPlaceholder('例：580').fill('600')
  await page.getByRole('button', { name: '儲存', exact: true }).click()

  await expect(page.getByRole('main').getByText('台積電')).toBeVisible()
})

test('new account can add its first watchlist stock', async ({ page }) => {
  let stockIds: string[] = []

  await page.route('**/api/**', async (route) => {
    const request = route.request()
    const pathname = new URL(request.url()).pathname
    if (pathname.startsWith('/api/auth/')) return route.continue()
    if (pathname === '/api/watchlists/default' && request.method() === 'PUT') {
      stockIds = request.postDataJSON().stocks
      return route.fulfill({ json: { message: '更新成功', id: 'default' } })
    }
    if (pathname === '/api/watchlists/default') {
      return route.fulfill({
        json: {
          id: 'default',
          name: 'default',
          stocks_count: stockIds.length,
          stocks: stockIds.map((stock_id) => ({
            stock_id,
            name: stock_id === '2330' ? '台積電' : stock_id,
            price: 600,
            change_pct: 1.5,
          })),
        },
      })
    }
    return route.fulfill({ status: 404, json: { detail: 'missing fixture' } })
  })

  await page.goto('/watchlist')
  await page.getByPlaceholder('輸入股票代號（例：2330）').fill('2330')
  await page.getByRole('button', { name: '新增自選' }).click()

  await expect(page.getByRole('main').getByText('台積電')).toBeVisible()
})

test('switching Google users never reuses the previous user cache', async ({
  context,
  page,
  baseURL,
}) => {
  let activeUser: 'alice' | 'bob' = 'alice'
  await page.route('**/api/**', async (route) => {
    const pathname = new URL(route.request().url()).pathname
    if (pathname.startsWith('/api/auth/')) return route.continue()
    if (pathname !== '/api/watchlists/default') {
      return route.fulfill({ status: 404, json: { detail: 'missing fixture' } })
    }
    if (activeUser === 'bob') {
      return route.fulfill({
        status: 503,
        json: { detail: 'bob has no cached response' },
      })
    }
    return route.fulfill({
      json: {
        id: 'default',
        name: 'default',
        stocks_count: 1,
        stocks: [
          {
            stock_id: '2330',
            name: 'Alice 專屬台積電',
            price: 600,
            change_pct: 1.5,
          },
        ],
      },
    })
  })

  await signInAsAllowedGoogleUser(
    context,
    baseURL ?? 'http://localhost:3000',
    'google_alice'
  )
  await page.goto('/watchlist')
  await expect(page.getByRole('main').getByText('Alice 專屬台積電')).toBeVisible()
  await expect(page.getByText(AUTH_EMAIL)).toBeVisible()
  await expect.poll(async () => {
    return page.evaluate(() => {
      window.dispatchEvent(new Event('beforeunload'))
      return Object.keys(localStorage)
    })
  }).toContain('swr-cache-v3:google_alice')
  const aliceCacheKeys = await page.evaluate(() => Object.keys(localStorage))
  expect(aliceCacheKeys).not.toContain('swr-cache-v2')

  activeUser = 'bob'
  await signInAsAllowedGoogleUser(
    context,
    baseURL ?? 'http://localhost:3000',
    'google_bob'
  )
  await page.reload()

  await expect(page.getByRole('main')).not.toContainText('Alice 專屬台積電')
  await expect.poll(async () => {
    return page.evaluate(() => {
      window.dispatchEvent(new Event('beforeunload'))
      return Object.keys(localStorage)
    })
  }).toContain('swr-cache-v3:google_bob')
})
