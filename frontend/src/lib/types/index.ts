// 市場摘要 — 對應 GET /market/summary
export interface MarketSummary {
  date: string
  taiex_index: number
  taiex_change: number
  total_stocks: number
  up_count: number
  down_count: number
  flat_count: number
  top_gainers: Array<{ stock_id: string; change_pct: number }>
  top_losers: Array<{ stock_id: string; change_pct: number }>
}

// 個股資訊 — 對應 GET /stock/:id
export interface StockInfo {
  stock_id: string
  name: string
  industry?: string
  latest_price: number
  change_pct: number
  date?: string
  pe_ratio?: number
  pb_ratio?: number
  dividend_yield?: number
  revenue_yoy?: number
  price_history?: Array<{ date: string; price: number }>
}

// 持倉
export interface Position {
  code: string
  name: string
  shares: number
  avgCost: number
  currentPrice: number
  unrealizedPnl: number
  unrealizedPnlPercent: number
  marketValue: number
}

// 警報
export interface Alert {
  id: string
  stock_id?: string
  code?: string
  name?: string
  type: 'price_above' | 'price_below' | 'rsi_above' | 'rsi_below' | 'volume_spike' | 'new_high' | 'new_low'
  value: number
  enabled: boolean
  triggered: boolean
  created_at?: string
  createdAt?: string
}

// 策略
export interface Strategy {
  id: string
  name: string
  description: string
  conditions: StrategyCondition[]
  createdAt: string
  updatedAt: string
}

export interface StrategyCondition {
  field: string
  operator: 'gt' | 'lt' | 'gte' | 'lte' | 'eq'
  value: number
}

// 技術指標
export interface TechnicalIndicators {
  ma5: number
  ma10: number
  ma20: number
  ma60: number
  rsi14: number
  macd: number
  macdSignal: number
  macdHistogram: number
  kdK: number
  kdD: number
  bollUpper: number
  bollMiddle: number
  bollLower: number
}

// OHLCV K 線資料
export interface OHLCVData {
  date: string
  open: number
  high: number
  low: number
  close: number
  volume: number
}

// API 回應通用格式
export interface ApiResponse<T> {
  data: T
  message?: string
  error?: string
}

// 分頁
export interface Pagination {
  page: number
  pageSize: number
  total: number
}

// 側邊欄導航項目
export interface NavItem {
  label: string
  href: string
  icon?: string
}

export interface NavGroup {
  label: string
  icon: string
  items: NavItem[]
}
