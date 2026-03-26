'use client'

import useSWR from 'swr'
import { fetchAPI } from '@/lib/api/client'
import { KpiCard } from '@/components/shared/KpiCard'
import { EmptyState } from '@/components/shared/EmptyState'
import { Skeleton } from '@/components/ui/skeleton'
import {
  formatCurrency,
  formatPercent,
  formatChange,
  getChangeColorVar,
} from '@/lib/utils/format'
import type { Position } from '@/lib/types'

interface Portfolio {
  totalAsset: number
  totalCost: number
  totalPnl: number
  totalPnlPercent: number
  positions: Position[]
}

function usePortfolio() {
  const { data, error, isLoading } = useSWR<Portfolio>(
    '/portfolios',
    (path: string) => fetchAPI<Portfolio>(path),
    { refreshInterval: 30000, revalidateOnFocus: true }
  )
  return { portfolio: data, isLoading, isError: !!error }
}

function PositionRowSkeleton() {
  return (
    <tr>
      {[...Array(7)].map((_, i) => (
        <td key={i} className="px-4 py-3">
          <Skeleton className="h-4 w-16" style={{ background: 'var(--secondary)' }} />
        </td>
      ))}
    </tr>
  )
}

export default function DashboardPage() {
  const { portfolio, isLoading, isError } = usePortfolio()

  const kpiCards = [
    {
      title: '總資產',
      value: isLoading ? '-' : formatCurrency(portfolio?.totalAsset ?? 0),
      accentColor: 'var(--primary)',
    },
    {
      title: '總成本',
      value: isLoading ? '-' : formatCurrency(portfolio?.totalCost ?? 0),
      accentColor: 'var(--muted-foreground)',
    },
    {
      title: '未實現損益',
      value: isLoading ? '-' : formatChange(portfolio?.totalPnl ?? 0),
      subValue: isLoading ? undefined : formatPercent(portfolio?.totalPnlPercent ?? 0),
      change: portfolio?.totalPnl,
      accentColor:
        portfolio?.totalPnl !== undefined
          ? getChangeColorVar(portfolio.totalPnl)
          : 'var(--primary)',
    },
  ]

  return (
    <div>
      {/* 頁面標題 */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold" style={{ color: 'var(--foreground)' }}>
          持倉總覽
        </h1>
        <p className="text-sm mt-1" style={{ color: 'var(--muted-foreground)' }}>
          投資組合損益即時追蹤
        </p>
      </div>

      {isError && (
        <EmptyState
          title="無法載入持倉資料"
          description="請確認後端服務是否正常運行，或稍後再試"
          icon="!"
        />
      )}

      {!isError && (
        <>
          {/* KPI 卡片 */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
            {kpiCards.map((card) => (
              <KpiCard
                key={card.title}
                isLoading={isLoading}
                accentColor={card.accentColor}
                title={card.title}
                value={card.value}
                subValue={card.subValue}
                change={card.change}
              />
            ))}
          </div>

          {/* 持股列表 */}
          <div
            className="rounded-lg overflow-hidden"
            style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
          >
            <div className="px-4 py-3 border-b" style={{ borderColor: 'var(--border)' }}>
              <h2 className="text-sm font-semibold" style={{ color: 'var(--foreground)' }}>
                持股明細
              </h2>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border)' }}>
                    {['代號', '名稱', '持股(張)', '成本價', '現價', '市值', '損益(%)'].map(
                      (h) => (
                        <th
                          key={h}
                          className="px-4 py-2 text-left font-medium"
                          style={{ color: 'var(--muted-foreground)' }}
                        >
                          {h}
                        </th>
                      )
                    )}
                  </tr>
                </thead>
                <tbody>
                  {isLoading
                    ? [...Array(5)].map((_, i) => <PositionRowSkeleton key={i} />)
                    : portfolio?.positions?.length
                    ? portfolio.positions.map((pos) => (
                        <tr
                          key={pos.code}
                          className="border-b transition-colors hover:bg-white/5"
                          style={{ borderColor: 'var(--border)' }}
                        >
                          <td
                            className="px-4 py-3 font-mono font-semibold"
                            style={{ color: 'var(--primary)' }}
                          >
                            {pos.code}
                          </td>
                          <td className="px-4 py-3" style={{ color: 'var(--foreground)' }}>
                            {pos.name}
                          </td>
                          <td
                            className="px-4 py-3 tabular-nums"
                            style={{ color: 'var(--foreground)' }}
                          >
                            {pos.shares.toLocaleString()}
                          </td>
                          <td
                            className="px-4 py-3 tabular-nums"
                            style={{ color: 'var(--foreground)' }}
                          >
                            {pos.avgCost.toFixed(2)}
                          </td>
                          <td
                            className="px-4 py-3 tabular-nums font-semibold"
                            style={{
                              color: getChangeColorVar(pos.currentPrice - pos.avgCost),
                            }}
                          >
                            {pos.currentPrice.toFixed(2)}
                          </td>
                          <td
                            className="px-4 py-3 tabular-nums"
                            style={{ color: 'var(--foreground)' }}
                          >
                            {formatCurrency(pos.marketValue)}
                          </td>
                          <td
                            className="px-4 py-3 tabular-nums font-semibold"
                            style={{ color: getChangeColorVar(pos.unrealizedPnl) }}
                          >
                            {formatChange(pos.unrealizedPnl)}
                            <span className="ml-1 text-xs opacity-75">
                              ({formatPercent(pos.unrealizedPnlPercent)})
                            </span>
                          </td>
                        </tr>
                      ))
                    : null}
                  {!isLoading && !portfolio?.positions?.length && (
                    <tr>
                      <td colSpan={7}>
                        <EmptyState
                          title="目前沒有持股"
                          description="尚未建立任何持倉紀錄"
                          icon="+"
                        />
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
