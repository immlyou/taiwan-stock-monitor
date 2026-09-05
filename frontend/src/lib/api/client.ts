// 客戶端走 Next.js route handler proxy (/api/* → Railway，server 端注入 Bearer token)
// 伺服器端（SSR / Server Components）直接打 Railway API 並自帶 token
//
// 生產環境必須在 Vercel 專案設定中加入：
//   NEXT_PUBLIC_API_URL = https://your-app.up.railway.app
//   STOCK_API_KEY       = <與 Railway 相同的金鑰>（server-only，不可加 NEXT_PUBLIC_ 前綴）
//
// 若未設定且非 localhost，則在建置時提早報錯而非靜默 timeout
const _rawApiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
if (
  typeof window === 'undefined' &&               // server-side only
  process.env.NODE_ENV === 'production' &&
  _rawApiUrl === 'http://localhost:8000'
) {
  // 非致命警告（不 throw，避免中斷 SSG），但會出現在 build log
  console.warn(
    '[taiwan-stock-monitor] NEXT_PUBLIC_API_URL 未設定。' +
    'Vercel SSR 中 localhost:8000 不可達，API 請求將失敗。' +
    '請在 Vercel 專案 → Settings → Environment Variables 中設定此變數。'
  )
}

const API_URL = typeof window !== 'undefined'
  ? '/api'
  : _rawApiUrl

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

export class QuotaExceededError extends Error {
  constructor() {
    super('API_QUOTA_EXCEEDED')
    this.name = 'QuotaExceededError'
  }
}

function isQuotaExceededText(text: string): boolean {
  return text.includes('Usage exceed') || text.includes('5000 MB')
}

// 重運算端點（回測、AI 選股、雷達）在雲端冷啟動 / 負載高時容易短暫回 503 或逾時。
// 對「冪等」請求（GET/HEAD）自動重試，讓使用者不必手動重整；非冪等（POST 等）
// 與 quota 超限一律不重試，避免重複送出或無謂打 API。
const RETRYABLE_STATUS = new Set([502, 503, 504])
const MAX_RETRIES = 1 // 共 2 次嘗試；SWR 不再額外疊加重試
const RETRY_BACKOFF_MS = [400]

function isIdempotent(method?: string): boolean {
  const m = (method ?? 'GET').toUpperCase()
  return m === 'GET' || m === 'HEAD'
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))

export async function fetchAPI<T>(
  path: string,
  options?: RequestInit,
  timeoutMs = 10000,
  maxRetries = MAX_RETRIES
): Promise<T> {
  const url = `${API_URL}${path}`

  // SSR / Server Components 直連 Railway，需自帶金鑰；
  // 瀏覽器端 process.env.STOCK_API_KEY 必為 undefined（非 NEXT_PUBLIC_，
  // 不會被打包進 client bundle），token 由 /api proxy 注入。
  const serverAuthHeaders: Record<string, string> =
    typeof window === 'undefined' && process.env.STOCK_API_KEY
      ? { Authorization: `Bearer ${process.env.STOCK_API_KEY}` }
      : {}

  // 單次嘗試：自帶 timeout 的 AbortController（每次重試都重新計時）。
  async function attempt(): Promise<T> {
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs)
    try {
      const response = await fetch(url, {
        ...options,
        headers: {
          'Content-Type': 'application/json',
          ...serverAuthHeaders,
          ...options?.headers,
        },
        signal: options?.signal ?? controller.signal,
      })

      const text = await response.text()

      if (isQuotaExceededText(text)) {
        throw new QuotaExceededError()
      }

      if (!response.ok) {
        throw new ApiError(response.status, text || `HTTP ${response.status}`)
      }

      // 解析 JSON 並檢查 degraded status（如 /health 端點）
      let data: T
      try {
        data = JSON.parse(text) as T
      } catch {
        return text as unknown as T
      }

      // 檢查回傳 200 但包含 quota 錯誤的情況（例如 health degraded）
      const anyData = data as Record<string, unknown>
      if (
        anyData &&
        typeof anyData === 'object' &&
        typeof anyData.error === 'string' &&
        isQuotaExceededText(anyData.error)
      ) {
        throw new QuotaExceededError()
      }

      return data
    } finally {
      clearTimeout(timeoutId)
    }
  }

  let lastErr: unknown
  const retryLimit = Math.max(0, Math.floor(maxRetries))
  for (let i = 0; i <= retryLimit; i++) {
    try {
      return await attempt()
    } catch (err) {
      lastErr = err
      // quota 超限是硬性限制，重試無益
      if (err instanceof QuotaExceededError) throw err
      // 呼叫端主動取消（傳入自己的 signal）不重試
      if (options?.signal?.aborted) throw err
      // 只對冪等請求重試；非冪等（POST 等）直接拋出避免重複送出
      if (!isIdempotent(options?.method)) throw err
      // 可重試的情況：閘道/服務暫時不可用（502/503/504）、逾時(AbortError)、網路層錯誤(TypeError)
      const retryable =
        (err instanceof ApiError && RETRYABLE_STATUS.has(err.status)) ||
        (err instanceof DOMException && err.name === 'AbortError') ||
        err instanceof TypeError
      if (!retryable || i === retryLimit) throw err
      await sleep(RETRY_BACKOFF_MS[i] ?? 1000)
    }
  }
  throw lastErr
}

// 系統相關 API
export interface RefreshResult {
  status: string
  refreshed: string[]
  failed: string[]
  latest_data_date: string | null
  timestamp: string
}

export const systemApi = {
  // 強制手動更新最新股票資料；重新下載可能耗時，逾時設定為 90 秒
  refresh: () =>
    fetchAPI<RefreshResult>('/refresh', { method: 'POST' }, 90000),
}

// 市場相關 API
export const marketApi = {
  getSummary: () => fetchAPI<Record<string, unknown>>('/market/summary'),
  getHeatmap: () => fetchAPI<Record<string, unknown>>('/market/heatmap'),
  getMoneyFlow: () => fetchAPI<Record<string, unknown>>('/market/money-flow'),
  getAfterHours: () => fetchAPI<Record<string, unknown>>('/market/after-hours'),
}

// 個股相關 API
export const stockApi = {
  search: (query: string) =>
    fetchAPI<Record<string, unknown>[]>(`/stocks/search?q=${encodeURIComponent(query)}`),
  getDetail: (code: string) =>
    fetchAPI<Record<string, unknown>>(`/stocks/${code}`),
  getTechnical: (code: string) =>
    fetchAPI<Record<string, unknown>>(`/stocks/${code}/technical`),
  getFinancials: (code: string) =>
    fetchAPI<Record<string, unknown>>(`/stocks/${code}/financials`),
  getChip: (code: string) =>
    fetchAPI<Record<string, unknown>>(`/stocks/${code}/chip`),
}

// 選股策略 API
export const strategyApi = {
  screen: (params: Record<string, unknown>) =>
    fetchAPI<Record<string, unknown>[]>('/strategy/screen', {
      method: 'POST',
      body: JSON.stringify(params),
    }),
  getStrategies: () => fetchAPI<Record<string, unknown>[]>('/strategy/list'),
  backtest: (params: Record<string, unknown>) =>
    fetchAPI<Record<string, unknown>>('/strategy/backtest', {
      method: 'POST',
      body: JSON.stringify(params),
    }),
}
