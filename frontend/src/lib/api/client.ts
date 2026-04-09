// 客戶端走 Next.js rewrite proxy (/api/* → Railway)
// 伺服器端（SSR / Server Components）直接打 Railway API
//
// 生產環境必須在 Vercel 專案設定中加入：
//   NEXT_PUBLIC_API_URL = https://your-app.up.railway.app
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

export async function fetchAPI<T>(
  path: string,
  options?: RequestInit,
  timeoutMs = 10000
): Promise<T> {
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs)

  const url = `${API_URL}${path}`

  try {
    const response = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
      ...options,
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
