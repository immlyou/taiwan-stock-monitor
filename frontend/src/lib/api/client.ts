// 客戶端走 Next.js rewrite proxy (/api/* → Railway)
// 伺服器端直接打 Railway API
const API_URL = typeof window !== 'undefined'
  ? '/api'
  : (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000')

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string
  ) {
    super(message)
    this.name = 'ApiError'
  }
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

    if (!response.ok) {
      const errorText = await response.text()
      throw new ApiError(response.status, errorText || `HTTP ${response.status}`)
    }

    return response.json() as Promise<T>
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
