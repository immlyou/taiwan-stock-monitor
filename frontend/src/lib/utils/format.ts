/**
 * 格式化金額（台幣）
 */
export function formatCurrency(
  value: number,
  options?: { compact?: boolean; decimals?: number }
): string {
  const { compact = false, decimals = 0 } = options ?? {}

  if (compact) {
    if (Math.abs(value) >= 1e8) {
      return `${(value / 1e8).toFixed(1)} 億`
    }
    if (Math.abs(value) >= 1e4) {
      return `${(value / 1e4).toFixed(1)} 萬`
    }
  }

  return new Intl.NumberFormat('zh-TW', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value)
}

/** 漲跌方向箭頭（雙重編碼用，避免僅靠顏色） */
export function changeArrow(value: number): string {
  if (value > 0) return '▲'
  if (value < 0) return '▼'
  return ''
}

/**
 * 格式化百分比
 * @param withArrow 是否前綴 ▲▼ 方向符號（色盲友善雙重編碼）
 */
export function formatPercent(value: number, decimals = 2, withArrow = false): string {
  const sign = value > 0 ? '+' : ''
  const arrow = withArrow && value !== 0 ? `${changeArrow(value)} ` : ''
  return `${arrow}${sign}${value.toFixed(decimals)}%`
}

/**
 * 格式化漲跌數字（帶正負號）
 * @param withArrow 是否前綴 ▲▼ 方向符號（色盲友善雙重編碼）
 */
export function formatChange(value: number, decimals = 2, withArrow = false): string {
  const sign = value > 0 ? '+' : ''
  const arrow = withArrow && value !== 0 ? `${changeArrow(value)} ` : ''
  return `${arrow}${sign}${value.toFixed(decimals)}`
}

/**
 * 取得漲跌顏色 class（台股：漲紅跌綠）
 */
export function getChangeColor(value: number): string {
  if (value > 0) return 'text-stock-up'
  if (value < 0) return 'text-stock-down'
  return 'text-stock-flat'
}

/**
 * 取得漲跌 CSS 變數色（用於 inline style）
 */
export function getChangeColorVar(value: number): string {
  if (value > 0) return 'var(--stock-up)'
  if (value < 0) return 'var(--stock-down)'
  return 'var(--stock-flat)'
}

/**
 * 格式化成交量（張數）
 */
export function formatVolume(shares: number): string {
  if (shares >= 1e4) {
    return `${(shares / 1e4).toFixed(2)} 萬張`
  }
  return `${formatCurrency(shares)} 張`
}

/**
 * 格式化成交金額（元）
 */
export function formatVolumeValue(value: number): string {
  if (value >= 1e8) {
    return `${(value / 1e8).toFixed(1)} 億元`
  }
  if (value >= 1e4) {
    return `${(value / 1e4).toFixed(1)} 萬元`
  }
  return `${formatCurrency(value)} 元`
}

/**
 * 格式化日期
 */
export function formatDate(
  dateStr: string,
  format: 'full' | 'short' | 'month-day' = 'full'
): string {
  const date = new Date(dateStr)
  if (format === 'short') {
    return `${date.getMonth() + 1}/${date.getDate()}`
  }
  if (format === 'month-day') {
    return `${date.getMonth() + 1} 月 ${date.getDate()} 日`
  }
  return `${date.getFullYear()}/${String(date.getMonth() + 1).padStart(2, '0')}/${String(date.getDate()).padStart(2, '0')}`
}

/**
 * 格式化股價（保留 2 位小數）
 */
export function formatPrice(price: number): string {
  return price.toFixed(2)
}

/**
 * 格式化大數字（萬、億）
 */
export function formatLargeNumber(value: number): string {
  if (Math.abs(value) >= 1e12) {
    return `${(value / 1e12).toFixed(2)} 兆`
  }
  if (Math.abs(value) >= 1e8) {
    return `${(value / 1e8).toFixed(2)} 億`
  }
  if (Math.abs(value) >= 1e4) {
    return `${(value / 1e4).toFixed(2)} 萬`
  }
  return String(value)
}
