export type QuoteSource = 'fugle' | 'twse' | 'finlab' | string
export type QuoteFreshness = 'realtime' | 'previous_close' | 'close' | string

export interface RealtimeQuote {
  stock_id: string
  name: string
  price: number
  prev_close?: number
  change?: number
  change_pct: number
  open?: number | null
  high?: number | null
  low?: number | null
  volume?: number | null
  amount?: number | null
  date?: string | null
  timestamp?: string | null
  source: QuoteSource
  is_realtime: boolean
  market_state: 'preopen' | 'trading' | 'closed' | string
  freshness: QuoteFreshness
  note?: string
}

interface QuoteStatus {
  source?: QuoteSource
  is_realtime?: boolean
  freshness?: QuoteFreshness
}

const SOURCE_LABELS: Record<string, string> = {
  fugle: 'Fugle',
  twse: 'TWSE',
  finlab: 'FinLab',
}

export function quoteStatusLabel(quote: QuoteStatus): string {
  if (quote.source === 'unavailable' || quote.freshness === 'unavailable') return '報價不可用'
  const source = SOURCE_LABELS[quote.source ?? ''] ?? quote.source ?? '未知來源'
  if (quote.is_realtime) return `即時 · ${source}`
  if (quote.source === 'finlab') return `收盤 · ${source}`
  if (quote.freshness === 'previous_close') return `盤前 · ${source}`
  return `休市 · ${source}`
}

export function quoteStatusColor(quote: QuoteStatus): string {
  if (quote.is_realtime) return 'var(--stock-up)'
  return 'var(--muted-foreground)'
}

export function quoteTimeLabel(quote: Pick<RealtimeQuote, 'timestamp' | 'date'>): string {
  if (quote.timestamp) {
    const date = new Date(quote.timestamp)
    if (!Number.isNaN(date.getTime())) {
      return new Intl.DateTimeFormat('zh-TW', {
        timeZone: 'Asia/Taipei',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hourCycle: 'h23',
      }).format(date)
    }
  }
  return quote.date ?? '—'
}

export function getQuoteRefreshInterval(now = new Date()): number {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: 'Asia/Taipei',
    weekday: 'short',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(now)
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]))
  if (values.weekday === 'Sat' || values.weekday === 'Sun') return 300_000
  const minutes = Number(values.hour) * 60 + Number(values.minute)
  if (minutes < 9 * 60) return 60_000
  if (minutes <= 13 * 60 + 30) return 15_000
  return 300_000
}

export function getBatchQuoteRefreshInterval(count: number, now = new Date()): number {
  const marketInterval = getQuoteRefreshInterval(now)
  const intervalForBudget = Math.ceil(Math.max(1, count) * 60_000 / 50)
  return Math.max(marketInterval, intervalForBudget)
}
