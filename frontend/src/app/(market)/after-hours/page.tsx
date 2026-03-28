'use client'

import { useState } from 'react'
import useSWR from 'swr'
import { fetchAPI } from '@/lib/api/client'
import { useMarketSummary } from '@/lib/hooks/useMarketSummary'
import { KpiCard } from '@/components/shared/KpiCard'
import { EmptyState } from '@/components/shared/EmptyState'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import {
  formatPercent,
  formatChange,
  getChangeColorVar,
} from '@/lib/utils/format'

// 對應 GET /market/after-hours
interface AfterHoursData {
  date: string
  market: {
    up: number
    down: number
    flat: number
  }
  top_gainers: Array<{ stock_id: string; name: string; change_pct: number }>
  top_losers: Array<{ stock_id: string; name: string; change_pct: number }>
  taiex?: {
    close: number
    change: number
    change_pct?: number
  }
  institutional?: {
    foreign?: { total_net?: number }
    trust?: { total_net?: number }
    dealer?: { total_net?: number }
  }
  ai_picks?: {
    value?: { total: number; top5: AiPickStock[] }
    growth?: { total: number; top5: AiPickStock[] }
    momentum?: { total: number; top5: AiPickStock[] }
  }
}

interface AiPickStock {
  stock_id: string
  name: string
}

function useAfterHours() {
  const { data, error, isLoading } = useSWR<AfterHoursData>(
    '/market/after-hours',
    (path: string) => fetchAPI<AfterHoursData>(path),
    { refreshInterval: 300000, revalidateOnFocus: false }
  )
  return { data, isLoading, isError: !!error }
}

// 三大法人股數（原始單位：股）→ 格式化為「張」
function formatShares(shares: number): string {
  const lots = shares / 1000
  const abs = Math.abs(lots)
  const sign = lots >= 0 ? '+' : ''
  if (abs >= 1e4) return `${sign}${(lots / 1e4).toFixed(1)} 萬張`
  if (abs >= 1e3) return `${sign}${(lots / 1e3).toFixed(1)} 千張`
  return `${sign}${lots.toFixed(0)} 張`
}

function AiPickList({
  category,
  isLoading,
}: {
  category: { total: number; top5: AiPickStock[] } | undefined
  isLoading: boolean
}) {
  if (isLoading) {
    return (
      <div className="space-y-3 p-4">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="flex items-center gap-4">
            <Skeleton className="h-4 w-12" style={{ background: 'var(--secondary)' }} />
            <Skeleton className="h-4 w-20" style={{ background: 'var(--secondary)' }} />
          </div>
        ))}
      </div>
    )
  }

  const stocks = category?.top5 ?? []

  if (!stocks.length) {
    return <EmptyState title="暫無策略選股結果" icon="+" />
  }

  return (
    <div className="p-4">
      {category && (
        <p className="text-xs mb-3" style={{ color: 'var(--muted-foreground)' }}>
          共 {category.total} 支符合條件，顯示前 {stocks.length} 支
        </p>
      )}
      <div className="space-y-2">
        {stocks.map((stock, i) => (
          <div
            key={stock.stock_id}
            className="flex items-center gap-3 py-2 border-b"
            style={{ borderColor: 'var(--border)' }}
          >
            <span
              className="text-xs tabular-nums w-5 text-center font-semibold"
              style={{ color: 'var(--muted-foreground)' }}
            >
              {i + 1}
            </span>
            <span className="font-mono font-semibold text-sm" style={{ color: 'var(--primary)' }}>
              {stock.stock_id}
            </span>
            <span className="text-sm" style={{ color: 'var(--foreground)' }}>
              {stock.name}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

function StockRankTable({
  title,
  stocks,
  isLoading,
}: {
  title: string
  stocks: Array<{ stock_id: string; name: string; change_pct: number }>
  isLoading: boolean
}) {
  return (
    <div
      className="rounded-lg overflow-hidden"
      style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
    >
      <div className="px-4 py-3 border-b" style={{ borderColor: 'var(--border)' }}>
        <h3 className="text-sm font-semibold" style={{ color: 'var(--foreground)' }}>{title}</h3>
      </div>
      {isLoading ? (
        <div className="space-y-2 p-4">
          {[...Array(5)].map((_, i) => (
            <Skeleton key={i} className="h-5 w-full" style={{ background: 'var(--secondary)' }} />
          ))}
        </div>
      ) : (
        <div className="p-3 space-y-2">
          {stocks.slice(0, 10).map((s) => (
            <div key={s.stock_id} className="flex items-center justify-between">
              <span className="text-xs">
                <span className="font-mono font-semibold" style={{ color: 'var(--primary)' }}>
                  {s.stock_id}
                </span>
                {s.name && (
                  <span className="ml-2" style={{ color: 'var(--foreground)' }}>{s.name}</span>
                )}
              </span>
              <span
                className="text-xs font-semibold tabular-nums"
                style={{ color: getChangeColorVar(s.change_pct) }}
              >
                {formatPercent(s.change_pct)}
              </span>
            </div>
          ))}
          {!stocks.length && (
            <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>暫無資料</p>
          )}
        </div>
      )}
    </div>
  )
}

interface AiSummaryResult {
  summary: string
  telegram_text: string
  error: string | null
}

export default function AfterHoursPage() {
  const { data, isLoading, isError } = useAfterHours()
  const { summary, isLoading: summaryLoading } = useMarketSummary()

  const [aiSummary, setAiSummary] = useState<AiSummaryResult | null>(null)
  const [aiLoading, setAiLoading] = useState(false)
  const [aiError, setAiError] = useState<string | null>(null)
  const [telegramOpen, setTelegramOpen] = useState(false)
  const [copied, setCopied] = useState(false)

  async function handleGenerateSummary() {
    setAiLoading(true)
    setAiError(null)
    setAiSummary(null)
    setTelegramOpen(false)
    try {
      const result = await fetchAPI<AiSummaryResult>('/ai/post-market-summary', {
        method: 'POST',
        body: JSON.stringify({ market_data: null }),
      })
      if (result.error) {
        setAiError(result.error)
      } else {
        setAiSummary(result)
      }
    } catch (err) {
      setAiError(err instanceof Error ? err.message : '生成失敗，請稍後再試')
    } finally {
      setAiLoading(false)
    }
  }

  async function handleCopyTelegram() {
    if (!aiSummary?.telegram_text) return
    try {
      await navigator.clipboard.writeText(aiSummary.telegram_text)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // fallback: ignore
    }
  }

  const taiex = data?.taiex
  const market = data?.market
  const inst = data?.institutional
  const aiPicks = data?.ai_picks

  // 加權指數收盤從 /market/summary 取，報酬指數 taiex.close 僅供參考
  const taiexIndex = summary?.taiex_index
  const taiexChange = taiex?.change
  const taiexChangePct = taiex?.change_pct

  // 三大法人：total_net 單位為「股」，格式化為「張」
  const foreignNet = inst?.foreign?.total_net ?? 0
  const trustNet = inst?.trust?.total_net ?? 0
  const dealerNet = inst?.dealer?.total_net ?? 0
  const instTotal = foreignNet + trustNet + dealerNet

  const combinedLoading = isLoading || summaryLoading

  const marketKpis = [
    {
      title: '收盤指數',
      value: combinedLoading ? '-' : taiexIndex != null ? taiexIndex.toFixed(2) : '-',
      change: taiexChange,
      changeLabel: taiexChangePct != null ? `${taiexChangePct > 0 ? '+' : ''}${taiexChangePct.toFixed(2)}%` : undefined,
      accentColor:
        taiexChange !== undefined
          ? getChangeColorVar(taiexChange)
          : 'var(--primary)',
    },
    {
      title: '漲跌點數',
      value: isLoading ? '-' : formatChange(taiexChange ?? 0),
      accentColor: taiexChange != null ? getChangeColorVar(taiexChange) : 'var(--primary)',
    },
    {
      title: '上漲家數',
      value: isLoading ? '-' : String(market?.up ?? 0),
      subValue: market ? `跌 ${market.down} 平 ${market.flat}` : undefined,
      accentColor: 'var(--stock-up)',
    },
    {
      title: '下跌家數',
      value: isLoading ? '-' : String(market?.down ?? 0),
      accentColor: 'var(--stock-down)',
    },
  ]

  const institutionalKpis = [
    {
      title: '外資買賣超',
      value: isLoading ? '-' : formatShares(foreignNet),
      change: foreignNet || undefined,
      accentColor: getChangeColorVar(foreignNet),
    },
    {
      title: '投信買賣超',
      value: isLoading ? '-' : formatShares(trustNet),
      change: trustNet || undefined,
      accentColor: getChangeColorVar(trustNet),
    },
    {
      title: '自營商買賣超',
      value: isLoading ? '-' : formatShares(dealerNet),
      change: dealerNet || undefined,
      accentColor: getChangeColorVar(dealerNet),
    },
    {
      title: '三大法人合計',
      value: isLoading ? '-' : formatShares(instTotal),
      change: instTotal || undefined,
      accentColor: getChangeColorVar(instTotal),
    },
  ]

  return (
    <div>
      {/* 頁面標題 */}
      <div className="mb-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold" style={{ color: 'var(--foreground)' }}>
              盤後總覽
            </h1>
            <p className="text-sm mt-1" style={{ color: 'var(--muted-foreground)' }}>
              {data?.date ? `${data.date} 收盤數據` : '每日盤後分析與 AI 策略選股'}
            </p>
          </div>
        </div>
      </div>

      {isError ? (
        <EmptyState
          title="無法載入盤後資料"
          description="請確認後端服務是否正常運行，或稍後再試"
          icon="!"
        />
      ) : (
        <div className="space-y-6">
          {/* 大盤收盤 KPI */}
          <section>
            <h2 className="text-xs font-semibold uppercase tracking-widest mb-3" style={{ color: 'var(--muted-foreground)' }}>
              大盤收盤數據
            </h2>
            <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
              {marketKpis.map((card) => (
                <KpiCard
                  key={card.title}
                  isLoading={combinedLoading}
                  accentColor={card.accentColor}
                  title={card.title}
                  value={card.value}
                  subValue={card.subValue}
                  change={card.change}
                  changeLabel={card.changeLabel}
                />
              ))}
            </div>
          </section>

          {/* 三大法人 KPI */}
          {inst && (
            <section>
              <h2 className="text-xs font-semibold uppercase tracking-widest mb-3" style={{ color: 'var(--muted-foreground)' }}>
                三大法人買賣超
              </h2>
              <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
                {institutionalKpis.map((card) => (
                  <KpiCard
                    key={card.title}
                    isLoading={isLoading}
                    accentColor={card.accentColor}
                    title={card.title}
                    value={card.value}
                    change={card.change}
                  />
                ))}
              </div>
            </section>
          )}

          {/* 漲跌幅排行 */}
          <section>
            <h2 className="text-xs font-semibold uppercase tracking-widest mb-3" style={{ color: 'var(--muted-foreground)' }}>
              漲跌幅排行
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <StockRankTable
                title="漲幅排行"
                stocks={data?.top_gainers ?? []}
                isLoading={isLoading}
              />
              <StockRankTable
                title="跌幅排行"
                stocks={data?.top_losers ?? []}
                isLoading={isLoading}
              />
            </div>
          </section>

          {/* AI 策略選股 */}
          {aiPicks && (
            <section>
              <h2 className="text-xs font-semibold uppercase tracking-widest mb-3" style={{ color: 'var(--muted-foreground)' }}>
                AI 策略選股
              </h2>
              <div
                className="rounded-lg overflow-hidden"
                style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
              >
                <Tabs defaultValue="value">
                  <div className="px-4 pt-4 border-b" style={{ borderColor: 'var(--border)' }}>
                    <TabsList
                      className="mb-0"
                      style={{ background: 'var(--secondary)' }}
                    >
                      <TabsTrigger value="value">價值型</TabsTrigger>
                      <TabsTrigger value="growth">成長型</TabsTrigger>
                      <TabsTrigger value="momentum">動能型</TabsTrigger>
                    </TabsList>
                  </div>
                  <TabsContent value="value">
                    <AiPickList category={aiPicks?.value} isLoading={isLoading} />
                  </TabsContent>
                  <TabsContent value="growth">
                    <AiPickList category={aiPicks?.growth} isLoading={isLoading} />
                  </TabsContent>
                  <TabsContent value="momentum">
                    <AiPickList category={aiPicks?.momentum} isLoading={isLoading} />
                  </TabsContent>
                </Tabs>
              </div>
            </section>
          )}

          {/* AI 盤後摘要 */}
          <section>
            <h2 className="text-xs font-semibold uppercase tracking-widest mb-3" style={{ color: 'var(--muted-foreground)' }}>
              🤖 AI 盤後摘要
            </h2>

            <button
              onClick={handleGenerateSummary}
              disabled={aiLoading}
              className="w-full py-3 px-4 rounded-lg text-sm font-semibold transition-opacity disabled:opacity-60"
              style={{
                background: 'var(--primary)',
                color: 'var(--primary-foreground)',
                cursor: aiLoading ? 'not-allowed' : 'pointer',
              }}
            >
              {aiLoading ? '⏳ 生成中，請稍候…' : '📝 生成 AI 覆盤報告'}
            </button>

            {aiError && (
              <div
                className="mt-4 rounded-lg px-4 py-3 text-sm"
                style={{ background: 'var(--destructive)', color: 'var(--destructive-foreground)' }}
              >
                錯誤：{aiError}
              </div>
            )}

            {aiLoading && (
              <div className="mt-4 space-y-3">
                <Skeleton className="h-4 w-3/4" style={{ background: 'var(--secondary)' }} />
                <Skeleton className="h-4 w-full" style={{ background: 'var(--secondary)' }} />
                <Skeleton className="h-4 w-5/6" style={{ background: 'var(--secondary)' }} />
                <Skeleton className="h-4 w-2/3" style={{ background: 'var(--secondary)' }} />
              </div>
            )}

            {aiSummary && (
              <div className="mt-4 space-y-4">
                {/* 完整報告 */}
                <div
                  className="rounded-lg p-5"
                  style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
                >
                  <h3
                    className="text-sm font-semibold mb-3"
                    style={{ color: 'var(--foreground)' }}
                  >
                    完整覆盤報告
                  </h3>
                  <p
                    className="text-sm leading-7 whitespace-pre-wrap"
                    style={{ color: 'var(--foreground)' }}
                  >
                    {aiSummary.summary}
                  </p>
                </div>

                {/* Telegram 精簡版（可折疊） */}
                <div
                  className="rounded-lg overflow-hidden"
                  style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
                >
                  <button
                    onClick={() => setTelegramOpen((v) => !v)}
                    className="w-full flex items-center justify-between px-5 py-3 text-sm font-semibold"
                    style={{ color: 'var(--foreground)' }}
                  >
                    <span>📨 Telegram 精簡版</span>
                    <span style={{ color: 'var(--muted-foreground)' }}>
                      {telegramOpen ? '▲ 收起' : '▼ 展開'}
                    </span>
                  </button>

                  {telegramOpen && (
                    <div className="px-5 pb-4 space-y-3">
                      <p
                        className="text-sm leading-7 whitespace-pre-wrap"
                        style={{ color: 'var(--foreground)' }}
                      >
                        {aiSummary.telegram_text}
                      </p>
                      <button
                        onClick={handleCopyTelegram}
                        className="mt-1 py-2 px-4 rounded-md text-xs font-semibold transition-opacity"
                        style={{
                          background: copied ? 'var(--stock-up)' : 'var(--secondary)',
                          color: copied ? '#fff' : 'var(--foreground)',
                        }}
                      >
                        {copied ? '✅ 已複製！' : '📋 複製到剪貼簿'}
                      </button>
                    </div>
                  )}
                </div>
              </div>
            )}
          </section>
        </div>
      )}
    </div>
  )
}
