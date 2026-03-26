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

interface AfterHoursData {
  date: string
  taiex: {
    close: number
    change: number
    changePercent: number
    volume: number
    volumeValue: number
    advances: number
    declines: number
    unchanged: number
  }
  institutional: {
    foreign: number
    investmentTrust: number
    dealer: number
    total: number
  }
  strategies: {
    profitFirst: StrategyStock[]
    shortMomentum: StrategyStock[]
    longHolding: StrategyStock[]
  }
}

interface StrategyStock {
  code: string
  name: string
  price: number
  changePercent: number
  reason: string
  score: number
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

function StrategyTable({
  stocks,
  isLoading,
}: {
  stocks: StrategyStock[]
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
              key={stock.code}
              className="border-b transition-colors hover:bg-white/5"
              style={{ borderColor: 'var(--border)' }}
            >
              <td className="px-4 py-3 font-mono font-semibold" style={{ color: 'var(--primary)' }}>
                {stock.code}
              </td>
              <td className="px-4 py-3" style={{ color: 'var(--foreground)' }}>
                {stock.name}
              </td>
              <td className="px-4 py-3 tabular-nums" style={{ color: 'var(--foreground)' }}>
                {stock.price.toFixed(2)}
              </td>
              <td
                className="px-4 py-3 tabular-nums font-semibold"
                style={{ color: getChangeColorVar(stock.changePercent) }}
              >
                {formatPercent(stock.changePercent)}
              </td>
              <td className="px-4 py-3 w-32">
                <ScoreBar score={stock.score} />
              </td>
              <td className="px-4 py-3 text-xs" style={{ color: 'var(--muted-foreground)' }}>
                {stock.reason}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function AfterHoursPage() {
  const { data, isLoading, isError } = useAfterHours()

  const taiex = data?.taiex
  const inst = data?.institutional
  const strategies = data?.strategies

  const marketKpis = [
    {
      title: '收盤指數',
      value: isLoading ? '-' : formatCurrency(taiex?.close ?? 0),
      change: taiex?.change,
      changeLabel: taiex ? formatPercent(taiex.changePercent) : undefined,
      accentColor:
        taiex?.change !== undefined
          ? getChangeColorVar(taiex.change)
          : 'var(--primary)',
    },
    {
      title: '漲跌點數',
      value: isLoading ? '-' : formatChange(taiex?.change ?? 0),
      subValue: taiex ? formatPercent(taiex.changePercent) : undefined,
      accentColor: 'var(--primary)',
    },
    {
      title: '成交量值',
      value: isLoading ? '-' : formatVolumeValue(taiex?.volumeValue ?? 0),
      accentColor: 'var(--primary)',
    },
    {
      title: '漲家',
      value: isLoading ? '-' : String(taiex?.advances ?? 0),
      subValue: taiex
        ? `跌 ${taiex.declines} 平 ${taiex.unchanged}`
        : undefined,
      accentColor: 'var(--stock-up)',
    },
  ]

  const institutionalKpis = [
    {
      title: '外資買賣超',
      value: isLoading ? '-' : formatVolumeValue(inst?.foreign ?? 0),
      change: inst?.foreign,
      accentColor:
        inst?.foreign !== undefined ? getChangeColorVar(inst.foreign) : 'var(--primary)',
    },
    {
      title: '投信買賣超',
      value: isLoading ? '-' : formatVolumeValue(inst?.investmentTrust ?? 0),
      change: inst?.investmentTrust,
      accentColor:
        inst?.investmentTrust !== undefined
          ? getChangeColorVar(inst.investmentTrust)
          : 'var(--primary)',
    },
    {
      title: '自營商買賣超',
      value: isLoading ? '-' : formatVolumeValue(inst?.dealer ?? 0),
      change: inst?.dealer,
      accentColor:
        inst?.dealer !== undefined ? getChangeColorVar(inst.dealer) : 'var(--primary)',
    },
    {
      title: '三大法人合計',
      value: isLoading ? '-' : formatVolumeValue(inst?.total ?? 0),
      change: inst?.total,
      accentColor:
        inst?.total !== undefined ? getChangeColorVar(inst.total) : 'var(--primary)',
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

          {/* AI 策略選股 */}
          <section>
            <h2 className="text-xs font-semibold uppercase tracking-widest mb-3" style={{ color: 'var(--muted-foreground)' }}>
              AI 策略選股
            </h2>
            <div
              className="rounded-lg overflow-hidden"
              style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
            >
              <Tabs defaultValue="profit">
                <div className="px-4 pt-4 border-b" style={{ borderColor: 'var(--border)' }}>
                  <TabsList
                    className="mb-0"
                    style={{ background: 'var(--secondary)' }}
                  >
                    <TabsTrigger value="profit">獲利優先</TabsTrigger>
                    <TabsTrigger value="momentum">短期動能</TabsTrigger>
                    <TabsTrigger value="longterm">長期存股</TabsTrigger>
                  </TabsList>
                </div>
                <TabsContent value="profit">
                  <StrategyTable
                    stocks={strategies?.profitFirst ?? []}
                    isLoading={isLoading}
                  />
                </TabsContent>
                <TabsContent value="momentum">
                  <StrategyTable
                    stocks={strategies?.shortMomentum ?? []}
                    isLoading={isLoading}
                  />
                </TabsContent>
                <TabsContent value="longterm">
                  <StrategyTable
                    stocks={strategies?.longHolding ?? []}
                    isLoading={isLoading}
                  />
                </TabsContent>
              </Tabs>
            </div>
          </section>
        </div>
      )}
    </div>
  )
}
