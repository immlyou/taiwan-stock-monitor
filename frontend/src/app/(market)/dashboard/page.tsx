'use client'

import useSWR from 'swr'
import { fetchAPI } from '@/lib/api/client'
import { KpiCard } from '@/components/shared/KpiCard'
import { EmptyState } from '@/components/shared/EmptyState'
import { Skeleton } from '@/components/ui/skeleton'
import {
  formatPrice,
  formatCurrency,
  formatPercent,
  formatChange,
  getChangeColorVar,
} from '@/lib/utils/format'

interface Holding {
  stock_id: string
  name?: string
  shares: number
  cost_price: number
  current_price?: number
  current_value?: number
  pnl?: number
  pnl_pct?: number
}

interface PortfolioSummary {
  total_cost: number
  total_value: number
  total_pnl: number
  total_pnl_pct: number
}

interface PortfolioDetail {
  id: string
  name: string
  holdings: Holding[]
  summary: PortfolioSummary
}

interface PortfolioListItem {
  id: string
  name: string
  holdings_count: number
}

interface PortfoliosListResponse {
  total: number
  portfolios: PortfolioListItem[]
}

interface DashboardWidget {
  id: string
  type: string
  enabled: boolean
  order: number
  size: string
  title: string
  config: Record<string, unknown>
}

interface DashboardConfig {
  updated_at: string
  widgets: DashboardWidget[]
}

interface SmartAlertsResponse {
  alerts: Array<{ stock_id: string; name?: string; severity: string; score?: number | null; reasons: string[] }>
}

interface IndustryRotation {
  industries: Array<{ industry: string; rotation_score: number; quadrant: string }>
}

interface ScoreUpgrades {
  upgrades: Array<{ stock_id: string; name?: string; score_change: number | null; rating: string }>
}

function useDashboard() {
  // Fetch portfolio list first
  const { data: listData, error: listError, isLoading: listLoading } =
    useSWR<PortfoliosListResponse>(
      '/portfolios',
      (path: string) => fetchAPI<PortfoliosListResponse>(path),
      { refreshInterval: 30000, revalidateOnFocus: true }
    )

  // Use first portfolio id if available, otherwise try 'default'
  const firstId = listData?.portfolios?.[0]?.id ?? null
  const portfolioId = firstId

  const { data: detail, error: detailError, isLoading: detailLoading } =
    useSWR<PortfolioDetail>(
      portfolioId ? `/portfolios/${portfolioId}` : null,
      (path: string) => fetchAPI<PortfolioDetail>(path),
      { refreshInterval: 30000, revalidateOnFocus: true }
    )

  const isLoading = listLoading || (!!portfolioId && detailLoading)
  const isError = !!listError || !!detailError

  return { detail, isLoading, isError, hasPortfolio: !!portfolioId }
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
  const { detail, isLoading, isError, hasPortfolio } = useDashboard()
  const { data: dashboardConfig } = useSWR<DashboardConfig>('/dashboard/config', fetchAPI)
  const { data: smartAlerts } = useSWR<SmartAlertsResponse>('/alerts/smart-preview?top_n=4', fetchAPI)
  const { data: rotation } = useSWR<IndustryRotation>('/market/industry-rotation?top_n=4', fetchAPI)
  const { data: scoreUpgrades } = useSWR<ScoreUpgrades>('/screener/score-upgrades?days=20&top_n=4', fetchAPI)

  const summary = detail?.summary
  const holdings = detail?.holdings ?? []
  const widgets = (dashboardConfig?.widgets ?? []).filter((widget) => widget.enabled).sort((a, b) => a.order - b.order)

  const kpiCards = [
    {
      title: '總資產',
      value: isLoading ? '-' : formatCurrency(summary?.total_value ?? 0),
      accentColor: 'var(--primary)',
    },
    {
      title: '總成本',
      value: isLoading ? '-' : formatCurrency(summary?.total_cost ?? 0),
      accentColor: 'var(--muted-foreground)',
    },
    {
      title: '未實現損益',
      value: isLoading ? '-' : formatChange(summary?.total_pnl ?? 0),
      subValue: isLoading ? undefined : formatPercent(summary?.total_pnl_pct ?? 0),
      change: summary?.total_pnl,
      accentColor:
        summary?.total_pnl !== undefined
          ? getChangeColorVar(summary.total_pnl)
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

          {widgets.length > 0 && (
            <div
              className="rounded-lg p-4 mb-6"
              style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
            >
              <div className="flex items-center justify-between mb-3">
                <div>
                  <h2 className="text-sm font-semibold" style={{ color: 'var(--foreground)' }}>自訂 Dashboard</h2>
                  <p className="text-xs mt-0.5" style={{ color: 'var(--muted-foreground)' }}>
                    Widget 設定由 /dashboard/config 管理
                  </p>
                </div>
                <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>{widgets.length} 個啟用</span>
              </div>
              <div className="grid md:grid-cols-3 gap-3">
                {widgets.slice(0, 6).map((widget) => (
                  <div key={widget.id} className="rounded-md p-3" style={{ background: 'var(--secondary)' }}>
                    <p className="text-xs mb-2" style={{ color: 'var(--muted-foreground)' }}>{widget.title}</p>
                    {widget.type === 'smart_alerts' ? (
                      <div className="space-y-1">
                        {(smartAlerts?.alerts ?? []).slice(0, 3).map((item) => (
                          <p key={item.stock_id} className="text-sm truncate" style={{ color: 'var(--foreground)' }}>
                            {item.stock_id} {item.reasons[0]}
                          </p>
                        ))}
                      </div>
                    ) : widget.type === 'industry_rotation' ? (
                      <div className="space-y-1">
                        {(rotation?.industries ?? []).slice(0, 3).map((item) => (
                          <p key={item.industry} className="text-sm flex justify-between gap-2" style={{ color: 'var(--foreground)' }}>
                            <span className="truncate">{item.industry}</span>
                            <span style={{ color: getChangeColorVar(item.rotation_score) }}>{item.quadrant}</span>
                          </p>
                        ))}
                      </div>
                    ) : widget.type === 'score_upgrades' ? (
                      <div className="space-y-1">
                        {(scoreUpgrades?.upgrades ?? []).slice(0, 3).map((item) => (
                          <p key={item.stock_id} className="text-sm flex justify-between gap-2" style={{ color: 'var(--foreground)' }}>
                            <span>{item.stock_id}</span>
                            <span style={{ color: getChangeColorVar(item.score_change ?? 0) }}>
                              {item.score_change != null && item.score_change > 0 ? '+' : ''}{item.score_change?.toFixed(1) ?? '—'}
                            </span>
                          </p>
                        ))}
                      </div>
                    ) : (
                      <p className="text-sm" style={{ color: 'var(--foreground)' }}>{widget.type}</p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

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
                    : holdings.length > 0
                    ? holdings.map((h) => {
                        const currentPrice = h.current_price ?? h.cost_price
                        const marketValue = h.current_value ?? h.shares * h.cost_price
                        const pnl = h.pnl ?? 0
                        const pnlPct = h.pnl_pct ?? 0
                        return (
                          <tr
                            key={h.stock_id}
                            className="border-b transition-colors hover:bg-white/5"
                            style={{ borderColor: 'var(--border)' }}
                          >
                            <td
                              className="px-4 py-3 font-mono font-semibold"
                              style={{ color: 'var(--primary)' }}
                            >
                              {h.stock_id}
                            </td>
                            <td className="px-4 py-3" style={{ color: 'var(--foreground)' }}>
                              {h.name ?? '—'}
                            </td>
                            <td
                              className="px-4 py-3 tabular-nums"
                              style={{ color: 'var(--foreground)' }}
                            >
                              {h.shares.toLocaleString()}
                            </td>
                            <td
                              className="px-4 py-3 tabular-nums"
                              style={{ color: 'var(--foreground)' }}
                            >
                              {formatPrice(h.cost_price)}
                            </td>
                            <td
                              className="px-4 py-3 tabular-nums font-semibold"
                              style={{
                                color: getChangeColorVar(currentPrice - h.cost_price),
                              }}
                            >
                              {formatPrice(currentPrice)}
                            </td>
                            <td
                              className="px-4 py-3 tabular-nums"
                              style={{ color: 'var(--foreground)' }}
                            >
                              {formatCurrency(marketValue)}
                            </td>
                            <td
                              className="px-4 py-3 tabular-nums font-semibold"
                              style={{ color: getChangeColorVar(pnl) }}
                            >
                              {formatChange(pnl)}
                              <span className="ml-1 text-xs opacity-75">
                                ({formatPercent(pnlPct)})
                              </span>
                            </td>
                          </tr>
                        )
                      })
                    : null}
                  {!isLoading && holdings.length === 0 && (
                    <tr>
                      <td colSpan={7}>
                        <EmptyState
                          title={hasPortfolio ? '目前沒有持股' : '尚未建立投資組合'}
                          description={hasPortfolio ? '尚未建立任何持倉紀錄' : '請前往投資組合頁面新增持股'}
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
