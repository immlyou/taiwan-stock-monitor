'use client'

import { useEffect, useState } from 'react'
import { useMarketSummary } from '@/lib/hooks/useMarketSummary'
import { formatCurrency, formatChange, formatPercent } from '@/lib/utils/format'

export const MARKET_TICKER_HEIGHT = 32

// 以 Asia/Taipei 取得台北當地的星期與時分（使用者本機時區無關）
function getTaipeiNowParts(): { day: number; mins: number } {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: 'Asia/Taipei',
    weekday: 'short',
    hour: 'numeric',
    minute: 'numeric',
    hour12: false,
  }).formatToParts(new Date())
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? ''
  const dayMap: Record<string, number> = {
    Sun: 0, Mon: 1, Tue: 2, Wed: 3, Thu: 4, Fri: 5, Sat: 6,
  }
  const day = dayMap[get('weekday')] ?? 0
  // hour12:false 在部分環境會把午夜回傳成 '24'
  const hour = Number(get('hour')) % 24
  const mins = hour * 60 + Number(get('minute'))
  return { day, mins }
}

function useIsMarketOpen() {
  const [open, setOpen] = useState(false)
  useEffect(() => {
    const check = () => {
      // 台股盤中 09:00–13:30，以台北時間判斷（非使用者本機時間）
      const { day, mins } = getTaipeiNowParts()
      setOpen(day >= 1 && day <= 5 && mins >= 540 && mins <= 810)
    }
    check()
    const id = setInterval(check, 60000)
    return () => clearInterval(id)
  }, [])
  return open
}

/**
 * 全域持久行情列（置於 Header 頂部，跨頁顯示市場脈絡）。
 * 對標 Bloomberg / TradingView 頂部行情條：加權指數、漲跌、漲跌家數、盤中/盤後。
 */
export function MarketTicker() {
  const { summary, isLoading } = useMarketSummary()
  const isOpen = useIsMarketOpen()

  const index = summary?.taiex_index ?? 0
  const change = summary?.taiex_change ?? 0
  const changePct =
    index > 0 && change !== 0 ? (change / (index - change)) * 100 : 0
  const up = change > 0
  const down = change < 0
  const indexColor = up ? 'var(--stock-up)' : down ? 'var(--stock-down)' : 'var(--stock-flat)'
  const arrow = up ? '▲' : down ? '▼' : '—'

  const upCount = summary?.up_count ?? 0
  const downCount = summary?.down_count ?? 0
  const flatCount = summary?.flat_count ?? 0

  return (
    <div
      className="flex items-center gap-4 px-3 md:px-4 overflow-x-auto whitespace-nowrap border-b text-xs"
      style={{
        height: MARKET_TICKER_HEIGHT,
        background: 'var(--background)',
        borderColor: 'var(--border)',
      }}
    >
      {/* 加權指數 */}
      <div className="flex items-center gap-1.5 shrink-0">
        <span style={{ color: 'var(--muted-foreground)' }}>加權</span>
        <span className="num font-semibold" style={{ color: 'var(--foreground)' }}>
          {isLoading ? '—' : formatCurrency(index, { decimals: 0 })}
        </span>
        {!isLoading && change !== 0 && (
          <span className="num font-medium" style={{ color: indexColor }}>
            {arrow} {formatChange(change)} ({formatPercent(changePct)})
          </span>
        )}
      </div>

      {/* 盤中 / 盤後 */}
      <span
        className="shrink-0 font-medium px-1.5 py-0.5 rounded"
        style={{
          color: isOpen ? 'var(--stock-down)' : 'var(--muted-foreground)',
          background: isOpen ? 'var(--stock-down-weak)' : 'transparent',
        }}
      >
        {isOpen ? '● 盤中' : '○ 盤後'}
      </span>

      {/* 漲跌家數 */}
      {!isLoading && (
        <div className="flex items-center gap-2 shrink-0">
          <span style={{ color: 'var(--stock-up)' }}>漲 {upCount}</span>
          <span style={{ color: 'var(--stock-flat)' }}>平 {flatCount}</span>
          <span style={{ color: 'var(--stock-down)' }}>跌 {downCount}</span>
        </div>
      )}

      {summary?.date && (
        <span className="shrink-0 ml-auto" style={{ color: 'var(--muted-foreground)' }}>
          {summary.date}
        </span>
      )}
    </div>
  )
}
