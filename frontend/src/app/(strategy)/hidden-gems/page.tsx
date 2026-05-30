'use client'

import { useState } from 'react'
import Link from 'next/link'
import useSWR from 'swr'
import { fetchAPI } from '@/lib/api/client'

// ── 型別定義 ──

interface StockScores {
  value: number
  revenue: number
  institutional: number
  technical: number
  small_cap: number
  ownership: number
  composite: number
}

interface GemStock {
  stock_id: string
  name: string
  price: number
  scores: StockScores
  tags: string[]
  highlight: string
  change_pct: number
}

interface ScanResult {
  scan_date: string
  total_scanned: number
  error?: string
  categories: {
    value_gems: GemStock[]
    revenue_breakout: GemStock[]
    stealth_buy: GemStock[]
    technical_reversal: GemStock[]
    small_cap_growth: GemStock[]
    ownership_shift: GemStock[]
  }
  composite_top20: GemStock[]
}

// ── Tab 定義 ──

type TabKey =
  | 'composite'
  | 'value_gems'
  | 'revenue_breakout'
  | 'stealth_buy'
  | 'technical_reversal'
  | 'small_cap_growth'
  | 'ownership_shift'

interface TabDef {
  key: TabKey
  label: string
  scoreKey: keyof StockScores
  desc: string
}

const TABS: TabDef[] = [
  { key: 'composite', label: '綜合排名', scoreKey: 'composite', desc: '6 大面向加權綜合評分 Top 20' },
  { key: 'value_gems', label: '低估價值', scoreKey: 'value', desc: 'PE<12 / PB<1 / 殖利率>5% / 冷門股' },
  { key: 'revenue_breakout', label: '營收爆發', scoreKey: 'revenue', desc: '營收 YoY>30% 但股價尚未反應' },
  { key: 'stealth_buy', label: '法人佈局', scoreKey: 'institutional', desc: '外資連買 + 投信買超，低調進場' },
  { key: 'technical_reversal', label: '技術反轉', scoreKey: 'technical', desc: 'RSI 超賣 + 布林下軌 + MACD 翻正' },
  { key: 'small_cap_growth', label: '小型成長', scoreKey: 'small_cap', desc: '低市值 + 高成長 + 合理 PE' },
  { key: 'ownership_shift', label: '籌碼集中', scoreKey: 'ownership', desc: '大戶增持 + 融資減 + 量縮惜售' },
]

// ── 分數顏色 ──

function scoreColor(score: number): string {
  if (score >= 80) return '#f59e0b' // 金色
  if (score >= 60) return '#3b82f6' // 藍色
  if (score >= 40) return '#9ca3af' // 灰色
  return '#4b5563' // 暗色
}

function changePctColor(pct: number): string {
  if (pct > 0) return '#ef4444'
  if (pct < 0) return '#22c55e'
  return 'var(--muted-foreground)'
}

// ── 主頁面 ──

export default function HiddenGemsPage() {
  const [activeTab, setActiveTab] = useState<TabKey>('composite')

  const { data, isLoading, error } = useSWR<ScanResult>(
    '/scanner/hidden-gems',
    () => fetchAPI<ScanResult>('/scanner/hidden-gems', undefined, 60000),
    { revalidateOnFocus: false, dedupingInterval: 300000 }
  )

  const currentTab = TABS.find((t) => t.key === activeTab)!

  // 取得當前 tab 的股票列表
  const getStocks = (): GemStock[] => {
    if (!data) return []
    if (activeTab === 'composite') return data.composite_top20 || []
    return (data.categories as Record<string, GemStock[]>)[activeTab] || []
  }

  const stocks = getStocks()

  // 統計
  const totalGems =
    data
      ? Object.values(data.categories).reduce((sum, arr) => sum + arr.length, 0)
      : 0

  return (
    <div>
      {/* 標題 */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold" style={{ color: 'var(--foreground)' }}>
          遺珠掃描器
        </h1>
        <p className="text-sm mt-1" style={{ color: 'var(--muted-foreground)' }}>
          全盤掃描台股市場，找出被忽略但潛力巨大的股票
        </p>
      </div>

      {/* 摘要卡片 */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-6">
        <SummaryCard label="掃描股數" value={data?.total_scanned ?? '--'} />
        <SummaryCard label="發現遺珠" value={totalGems || '--'} accent />
        <SummaryCard label="掃描日期" value={data?.scan_date ?? '--'} />
      </div>

      {/* Tab 列 */}
      <div
        className="flex gap-1 overflow-x-auto pb-1 mb-4"
        style={{ scrollbarWidth: 'thin' }}
      >
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className="shrink-0 px-3 py-1.5 rounded-md text-xs font-medium transition-colors whitespace-nowrap"
            style={{
              background: activeTab === tab.key ? 'var(--primary)' : 'var(--secondary)',
              color: activeTab === tab.key ? 'var(--primary-foreground)' : 'var(--foreground)',
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab 說明 */}
      <p className="text-xs mb-4" style={{ color: 'var(--muted-foreground)' }}>
        {currentTab.desc}
      </p>

      {/* 內容區 */}
      {error ? (
        <Card>
          <p className="text-center py-8" style={{ color: 'var(--destructive)' }}>
            掃描失敗，請稍後再試
          </p>
        </Card>
      ) : isLoading ? (
        <Card>
          <p className="text-center py-8" style={{ color: 'var(--muted-foreground)' }}>
            全盤掃描中，預計需要 10-30 秒...
          </p>
        </Card>
      ) : data?.error ? (
        <Card>
          <p className="text-center py-8" style={{ color: 'var(--destructive)' }}>
            {data.error}
          </p>
        </Card>
      ) : stocks.length === 0 ? (
        <Card>
          <p className="text-center py-8" style={{ color: 'var(--muted-foreground)' }}>
            此面向暫無符合條件的股票
          </p>
        </Card>
      ) : (
        <div className="grid gap-3">
          {stocks.map((stock, idx) => (
            <StockCard
              key={stock.stock_id}
              stock={stock}
              rank={idx + 1}
              scoreKey={currentTab.scoreKey}
              scoreLabel={currentTab.label}
            />
          ))}
        </div>
      )}
    </div>
  )
}

// ── 子元件 ──

function Card({ children }: { children: React.ReactNode }) {
  return (
    <div
      className="rounded-lg"
      style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
    >
      {children}
    </div>
  )
}

function SummaryCard({
  label,
  value,
  accent,
}: {
  label: string
  value: string | number
  accent?: boolean
}) {
  return (
    <div
      className="rounded-lg p-4"
      style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
    >
      <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
        {label}
      </p>
      <p
        className="text-lg font-bold mt-1 tabular-nums"
        style={{ color: accent ? '#f59e0b' : 'var(--foreground)' }}
      >
        {value}
      </p>
    </div>
  )
}

function StockCard({
  stock,
  rank,
  scoreKey,
  scoreLabel,
}: {
  stock: GemStock
  rank: number
  scoreKey: keyof StockScores
  scoreLabel: string
}) {
  const score = stock.scores[scoreKey] ?? 0
  const color = scoreColor(score)
  const scoreValue = Math.round(score)

  return (
    <div
      className="rounded-lg p-4 flex flex-col gap-3 sm:flex-row sm:items-center transition-colors hover:border-[var(--primary)]"
      style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
    >
      {/* 排名 + 基本資訊 */}
      <div className="flex items-center gap-3 min-w-0 sm:w-[240px] shrink-0">
        <span
          className="text-xs font-bold w-6 h-6 flex items-center justify-center rounded-full shrink-0"
          style={{
            background: rank <= 3 ? '#f59e0b' : 'var(--secondary)',
            color: rank <= 3 ? '#fff' : 'var(--muted-foreground)',
          }}
        >
          {rank}
        </span>
        <div className="min-w-0">
          <Link
            href={`/stock/${stock.stock_id}`}
            className="flex items-center gap-2 group"
          >
            <span className="text-sm font-semibold group-hover:underline" style={{ color: 'var(--primary)' }}>
              {stock.stock_id}
            </span>
            <span className="text-sm truncate group-hover:underline" style={{ color: 'var(--foreground)' }}>
              {stock.name || '--'}
            </span>
            <span className="text-xs opacity-0 group-hover:opacity-100 transition-opacity" style={{ color: 'var(--primary)' }}>
              →
            </span>
          </Link>
          <div className="flex items-center gap-2 mt-0.5">
            <span className="text-xs tabular-nums" style={{ color: 'var(--foreground)' }}>
              ${stock.price.toFixed(2)}
            </span>
            <span
              className="text-xs tabular-nums font-medium"
              style={{ color: changePctColor(stock.change_pct) }}
            >
              {stock.change_pct > 0 ? '+' : ''}
              {stock.change_pct.toFixed(1)}%
            </span>
          </div>
        </div>
      </div>

      {/* 分數條 */}
      <div className="flex items-center gap-2 sm:w-[160px] shrink-0">
        <div
          role="progressbar"
          aria-valuenow={scoreValue}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`${stock.stock_id} ${scoreLabel}分數 ${scoreValue} 分（滿分 100）`}
          className="flex-1 h-2 rounded-full overflow-hidden"
          style={{ background: 'var(--secondary)' }}
        >
          <div
            className="h-full rounded-full transition-all"
            style={{ width: `${Math.min(score, 100)}%`, background: color }}
          />
        </div>
        <span
          className="text-xs font-bold tabular-nums w-8 text-right"
          style={{ color }}
        >
          {score.toFixed(0)}
        </span>
      </div>

      {/* 標籤 + 亮點 */}
      <div className="flex-1 min-w-0">
        {stock.tags.length > 0 && (
          <div className="flex flex-wrap gap-1 mb-1">
            {stock.tags.map((tag) => (
              <span
                key={tag}
                className="text-[10px] px-1.5 py-0.5 rounded"
                style={{
                  background: 'var(--secondary)',
                  color: 'var(--muted-foreground)',
                }}
              >
                {tag}
              </span>
            ))}
          </div>
        )}
        {stock.highlight && (
          <p
            className="text-xs truncate"
            style={{ color: 'var(--muted-foreground)' }}
            title={stock.highlight}
          >
            {stock.highlight}
          </p>
        )}
      </div>
    </div>
  )
}
