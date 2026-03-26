'use client'

import useSWR from 'swr'
import { fetchAPI } from '@/lib/api/client'
import { KpiCard } from '@/components/shared/KpiCard'
import { EmptyState } from '@/components/shared/EmptyState'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import {
  formatCurrency,
  formatPercent,
  formatChange,
  formatVolumeValue,
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
    volume?: number
  }
  institutional?: {
    foreign?: { net?: number; total_net?: number }
    trust?: { net?: number; total_net?: number }
    dealer?: { net?: number; total_net?: number }
  }
  ai_picks?: {
    value?: AiPickStock[]
    momentum?: AiPickStock[]
    savings?: AiPickStock[]
  }
}

interface AiPickStock {
  stock_id: string
  name: string
  price?: number
  change_pct?: number
  reason?: string
  score?: number
}

function useAfterHours() {
  const { data, error, isLoading } = useSWR<AfterHoursData>(
    '/market/after-hours',
    (path: string) => fetchAPI<AfterHoursData>(path),
    { refreshInterval: 300000, revalidateOnFocus: false }
  )
  return { data, isLoading, isError: !!error }
}

function ScoreBar({ score }: { score: number }) {
  const pct = Math.min(100, Math.max(0, score))
  const color = pct >= 70 ? 'var(--stock-up)' : pct >= 40 ? '#f59e0b' : 'var(--stock-down)'
  return (
    <div className="flex items-center gap-2">
      <div
        className="flex-1 rounded-full h-1.5 overflow-hidden"
        style={{ background: 'var(--secondary)' }}
      >
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
      <span className="text-xs tabular-nums w-8 text-right" style={{ color: 'var(--muted-foreground)' }}>
        {score}
      </span>
    </div>
  )
}

function AiPickTable({
  stocks,
  isLoading,
}: {
  stocks: AiPickStock[]
  isLoading: boolean
}) {
  if (isLoading) {
    return (
      <div className="space-y-3 p-4">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="flex items-center gap-4">
            <Skeleton className="h-4 w-12" style={{ background: 'var(--secondary)' }} />
            <Skeleton className="h-4 w-20" style={{ background: 'var(--secondary)' }} />
            <Skeleton className="h-4 flex-1" style={{ background: 'var(--secondary)' }} />
          </div>
        ))}
      </div>
    )
  }

  if (!stocks?.length) {
    return <EmptyState title="暫無策略選股結果" icon="+" />
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr style={{ borderBottom: '1px solid var(--border)' }}>
            {['代號', '名稱', '現價', '漲跌幅', '評分', '入選原因'].map((h) => (
              <th
                key={h}
                className="px-4 py-2 text-left font-medium"
                style={{ color: 'var(--muted-foreground)' }}
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {stocks.map((stock) => (
            <tr
              key={stock.stock_id}
              className="border-b transition-colors hover:bg-white/5"
              style={{ borderColor: 'var(--border)' }}
            >
              <td className="px-4 py-3 font-mono font-semibold" style={{ color: 'var(--primary)' }}>
                {stock.stock_id}
              </td>
              <td className="px-4 py-3" style={{ color: 'var(--foreground)' }}>
                {stock.name}
              </td>
              <td className="px-4 py-3 tabular-nums" style={{ color: 'var(--foreground)' }}>
                {stock.price != null ? stock.price.toFixed(2) : '—'}
              </td>
              <td
                className="px-4 py-3 tabular-nums font-semibold"
                style={{ color: getChangeColorVar(stock.change_pct ?? 0) }}
              >
                {stock.change_pct != null ? formatPercent(stock.change_pct) : '—'}
              </td>
              <td className="px-4 py-3 w-32">
                {stock.score != null ? <ScoreBar score={stock.score} /> : '—'}
              </td>
              <td className="px-4 py-3 text-xs" style={{ color: 'var(--muted-foreground)' }}>
                {stock.reason ?? '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
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

export default function AfterHoursPage() {
  const { data, isLoading, isError } = useAfterHours()

  const taiex = data?.taiex
  const market = data?.market
  const inst = data?.institutional
  const aiPicks = data?.ai_picks

  // 取各法人 total_net（有些 API 回傳 total_net，有些回傳 net）
  const foreignNet = inst?.foreign?.total_net ?? inst?.foreign?.net ?? 0
  const trustNet = inst?.trust?.total_net ?? inst?.trust?.net ?? 0
  const dealerNet = inst?.dealer?.total_net ?? inst?.dealer?.net ?? 0
  const instTotal = foreignNet + trustNet + dealerNet

  const marketKpis = [
    {
      title: '收盤指數',
      value: isLoading ? '-' : formatCurrency(taiex?.close ?? 0),
      change: taiex?.change,
      changeLabel: taiex?.change != null && taiex?.close != null && taiex.close > 0
        ? formatPercent((taiex.change / (taiex.close - taiex.change)) * 100)
        : undefined,
      accentColor:
        taiex?.change !== undefined
          ? getChangeColorVar(taiex.change)
          : 'var(--primary)',
    },
    {
      title: '漲跌點數',
      value: isLoading ? '-' : formatChange(taiex?.change ?? 0),
      accentColor: 'var(--primary)',
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
      value: isLoading ? '-' : formatVolumeValue(foreignNet),
      change: foreignNet || undefined,
      accentColor: getChangeColorVar(foreignNet),
    },
    {
      title: '投信買賣超',
      value: isLoading ? '-' : formatVolumeValue(trustNet),
      change: trustNet || undefined,
      accentColor: getChangeColorVar(trustNet),
    },
    {
      title: '自營商買賣超',
      value: isLoading ? '-' : formatVolumeValue(dealerNet),
      change: dealerNet || undefined,
      accentColor: getChangeColorVar(dealerNet),
    },
    {
      title: '三大法人合計',
      value: isLoading ? '-' : formatVolumeValue(instTotal),
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
                  isLoading={isLoading}
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
                      <TabsTrigger value="value">價值優先</TabsTrigger>
                      <TabsTrigger value="momentum">短期動能</TabsTrigger>
                      <TabsTrigger value="savings">長期存股</TabsTrigger>
                    </TabsList>
                  </div>
                  <TabsContent value="value">
                    <AiPickTable
                      stocks={aiPicks?.value ?? []}
                      isLoading={isLoading}
                    />
                  </TabsContent>
                  <TabsContent value="momentum">
                    <AiPickTable
                      stocks={aiPicks?.momentum ?? []}
                      isLoading={isLoading}
                    />
                  </TabsContent>
                  <TabsContent value="savings">
                    <AiPickTable
                      stocks={aiPicks?.savings ?? []}
                      isLoading={isLoading}
                    />
                  </TabsContent>
                </Tabs>
              </div>
            </section>
          )}
        </div>
      )}
    </div>
  )
}
