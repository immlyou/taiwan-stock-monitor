'use client'

import useSWR from 'swr'
import { fetchAPI } from '@/lib/api/client'
import { KpiCard } from '@/components/shared/KpiCard'
import { EmptyState } from '@/components/shared/EmptyState'
import { Skeleton } from '@/components/ui/skeleton'
import {
  formatVolumeValue,
  formatChange,
  getChangeColorVar,
} from '@/lib/utils/format'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Cell,
} from 'recharts'

interface InstitutionalFlow {
  date: string
  foreign: number
  investmentTrust: number
  dealer: number
  total: number
}

interface ConsecutiveBuyer {
  code: string
  name: string
  consecutiveDays: number
  totalNetBuy: number
  institution: string
}

interface MoneyFlowData {
  summary: {
    foreign: number
    investmentTrust: number
    dealer: number
    total: number
  }
  trend: InstitutionalFlow[]
  consecutiveBuyers: ConsecutiveBuyer[]
  updatedAt: string
}

function useMoneyFlow() {
  const { data, error, isLoading } = useSWR<MoneyFlowData>(
    '/market/money-flow',
    (path: string) => fetchAPI<MoneyFlowData>(path),
    { refreshInterval: 60000, revalidateOnFocus: true }
  )
  return { data, isLoading, isError: !!error }
}

interface CustomTooltipProps {
  active?: boolean
  payload?: Array<{ name: string; value: number; color: string }>
  label?: string
}

function CustomBarTooltip({ active, payload, label }: CustomTooltipProps) {
  if (!active || !payload?.length) return null
  return (
    <div
      className="rounded-lg p-3 text-xs shadow-lg"
      style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
    >
      <p className="font-semibold mb-2" style={{ color: 'var(--foreground)' }}>
        {label}
      </p>
      {payload.map((entry) => (
        <div key={entry.name} className="flex items-center justify-between gap-4">
          <span style={{ color: entry.color }}>{entry.name}</span>
          <span
            className="tabular-nums font-semibold"
            style={{ color: entry.value >= 0 ? 'var(--stock-up)' : 'var(--stock-down)' }}
          >
            {formatChange(entry.value / 1e8)} 億
          </span>
        </div>
      ))}
    </div>
  )
}

export default function MoneyFlowPage() {
  const { data, isLoading, isError } = useMoneyFlow()

  const summary = data?.summary
  const trend = data?.trend ?? []
  const buyers = data?.consecutiveBuyers ?? []

  const kpiCards = [
    {
      title: '外資買賣超',
      value: isLoading ? '-' : formatVolumeValue(summary?.foreign ?? 0),
      change: summary?.foreign,
      accentColor:
        summary?.foreign !== undefined
          ? getChangeColorVar(summary.foreign)
          : 'var(--primary)',
    },
    {
      title: '投信買賣超',
      value: isLoading ? '-' : formatVolumeValue(summary?.investmentTrust ?? 0),
      change: summary?.investmentTrust,
      accentColor:
        summary?.investmentTrust !== undefined
          ? getChangeColorVar(summary.investmentTrust)
          : 'var(--primary)',
    },
    {
      title: '自營商買賣超',
      value: isLoading ? '-' : formatVolumeValue(summary?.dealer ?? 0),
      change: summary?.dealer,
      accentColor:
        summary?.dealer !== undefined
          ? getChangeColorVar(summary.dealer)
          : 'var(--primary)',
    },
    {
      title: '三大法人合計',
      value: isLoading ? '-' : formatVolumeValue(summary?.total ?? 0),
      change: summary?.total,
      accentColor:
        summary?.total !== undefined
          ? getChangeColorVar(summary.total)
          : 'var(--primary)',
    },
  ]

  const chartData = trend.map((d) => ({
    date: d.date.slice(5), // MM-DD
    外資: d.foreign,
    投信: d.investmentTrust,
    自營商: d.dealer,
  }))

  return (
    <div>
      {/* 頁面標題 */}
      <div className="mb-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold" style={{ color: 'var(--foreground)' }}>
              資金流向
            </h1>
            <p className="text-sm mt-1" style={{ color: 'var(--muted-foreground)' }}>
              三大法人買賣超分析
            </p>
          </div>
          {data?.updatedAt && (
            <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
              更新：{new Date(data.updatedAt).toLocaleTimeString('zh-TW')}
            </span>
          )}
        </div>
      </div>

      {isError ? (
        <EmptyState
          title="無法載入資金流向資料"
          description="請確認後端服務是否正常運行，或稍後再試"
          icon="!"
        />
      ) : (
        <div className="space-y-6">
          {/* KPI 卡片 */}
          <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
            {kpiCards.map((card) => (
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

          {/* 趨勢圖 */}
          <div
            className="rounded-lg p-5"
            style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
          >
            <h2 className="text-sm font-semibold mb-4" style={{ color: 'var(--foreground)' }}>
              法人買賣超趨勢
            </h2>
            {isLoading ? (
              <Skeleton className="h-64 w-full" style={{ background: 'var(--secondary)' }} />
            ) : chartData.length === 0 ? (
              <EmptyState title="暫無趨勢資料" icon="+" />
            ) : (
              <div style={{ height: 300 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chartData} margin={{ top: 5, right: 10, left: 10, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                    <XAxis
                      dataKey="date"
                      tick={{ fill: 'var(--muted-foreground)', fontSize: 11 }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <YAxis
                      tickFormatter={(v: number) => `${(v / 1e8).toFixed(0)}億`}
                      tick={{ fill: 'var(--muted-foreground)', fontSize: 11 }}
                      axisLine={false}
                      tickLine={false}
                      width={55}
                    />
                    <Tooltip content={<CustomBarTooltip />} cursor={{ fill: 'var(--secondary)' }} />
                    <Legend
                      wrapperStyle={{ fontSize: 12, color: 'var(--muted-foreground)' }}
                    />
                    <Bar dataKey="外資" radius={[2, 2, 0, 0]}>
                      {chartData.map((entry, index) => (
                        <Cell
                          key={index}
                          fill={(entry['外資'] as number) >= 0 ? 'var(--stock-up)' : 'var(--stock-down)'}
                        />
                      ))}
                    </Bar>
                    <Bar dataKey="投信" radius={[2, 2, 0, 0]}>
                      {chartData.map((entry, index) => (
                        <Cell
                          key={index}
                          fill={(entry['投信'] as number) >= 0 ? '#f97316' : '#fb923c'}
                        />
                      ))}
                    </Bar>
                    <Bar dataKey="自營商" radius={[2, 2, 0, 0]}>
                      {chartData.map((entry, index) => (
                        <Cell
                          key={index}
                          fill={(entry['自營商'] as number) >= 0 ? '#a855f7' : '#c084fc'}
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>

          {/* 連續買超排行 */}
          <div
            className="rounded-lg overflow-hidden"
            style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
          >
            <div className="px-5 py-3 border-b" style={{ borderColor: 'var(--border)' }}>
              <h2 className="text-sm font-semibold" style={{ color: 'var(--foreground)' }}>
                法人連續買超排行
              </h2>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border)' }}>
                    {['代號', '名稱', '法人', '連續買超(日)', '累計買超金額'].map((h) => (
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
                  {isLoading
                    ? [...Array(5)].map((_, i) => (
                        <tr key={i}>
                          {[...Array(5)].map((_, j) => (
                            <td key={j} className="px-4 py-3">
                              <Skeleton className="h-4 w-16" style={{ background: 'var(--secondary)' }} />
                            </td>
                          ))}
                        </tr>
                      ))
                    : buyers.length > 0
                    ? buyers.map((buyer) => (
                        <tr
                          key={`${buyer.code}-${buyer.institution}`}
                          className="border-b transition-colors hover:bg-white/5"
                          style={{ borderColor: 'var(--border)' }}
                        >
                          <td className="px-4 py-3 font-mono font-semibold" style={{ color: 'var(--primary)' }}>
                            {buyer.code}
                          </td>
                          <td className="px-4 py-3" style={{ color: 'var(--foreground)' }}>
                            {buyer.name}
                          </td>
                          <td className="px-4 py-3" style={{ color: 'var(--muted-foreground)' }}>
                            {buyer.institution}
                          </td>
                          <td
                            className="px-4 py-3 tabular-nums font-bold"
                            style={{ color: 'var(--stock-up)' }}
                          >
                            {buyer.consecutiveDays} 日
                          </td>
                          <td
                            className="px-4 py-3 tabular-nums"
                            style={{ color: 'var(--stock-up)' }}
                          >
                            {formatVolumeValue(buyer.totalNetBuy)}
                          </td>
                        </tr>
                      ))
                    : null}
                  {!isLoading && buyers.length === 0 && (
                    <tr>
                      <td colSpan={5}>
                        <EmptyState title="暫無連續買超資料" icon="+" />
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
