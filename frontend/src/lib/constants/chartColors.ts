/**
 * 集中圖表與語意色彩來源（皆指向 globals.css 的設計 token）。
 * 各頁圖表線色/評級色/法人色一律從此引用，取代散落的硬編 hex。
 */

/** 漲跌（台股：紅漲綠跌） */
export const UP = 'var(--stock-up)'
export const DOWN = 'var(--stock-down)'
export const FLAT = 'var(--stock-flat)'

/** 三大法人 / 資金分類色 */
export const FLOW = {
  foreign: 'var(--flow-foreign)',
  trust: 'var(--flow-trust)',
  dealer: 'var(--flow-dealer)',
} as const

/** 多序列圖表色盤（指標、比較線等依序取用） */
export const CHART_SERIES = [
  'var(--chart-1)',
  'var(--chart-2)',
  'var(--chart-3)',
  'var(--chart-4)',
  'var(--chart-5)',
  'var(--chart-6)',
] as const

/** 技術指標常用線色 */
export const INDICATOR = {
  ma5: 'var(--chart-1)',
  ma20: 'var(--chart-2)',
  ma60: 'var(--chart-3)',
  rsi: 'var(--chart-4)',
  macd: 'var(--chart-3)',
  signal: 'var(--chart-2)',
} as const

/** 量化評級色（A→F） */
export function ratingColor(rating: string): string {
  switch (rating?.toUpperCase()) {
    case 'A':
      return 'var(--rating-a)'
    case 'B':
      return 'var(--rating-b)'
    case 'C':
      return 'var(--rating-c)'
    case 'D':
      return 'var(--rating-d)'
    case 'F':
      return 'var(--rating-f)'
    default:
      return 'var(--muted-foreground)'
  }
}
