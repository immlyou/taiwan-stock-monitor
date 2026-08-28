'use client'

import { useState } from 'react'
import useSWR from 'swr'
import type { ColumnDef } from '@tanstack/react-table'
import { fetchAPI } from '@/lib/api/client'
import { KpiCard } from '@/components/shared/KpiCard'
import { EmptyState } from '@/components/shared/EmptyState'
import { StaleBanner } from '@/components/shared/StaleBanner'
import { DataTable } from '@/components/shared/DataTable'
import { Sparkline } from '@/components/shared/Sparkline'
import { Skeleton } from '@/components/ui/skeleton'
import { Switch } from '@/components/ui/switch'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import {
  formatPrice,
  formatCurrency,
  formatPercent,
  formatChange,
  getChangeColorVar,
} from '@/lib/utils/format'
import type { MarketSummary } from '@/lib/types'
import { isSupportedDashboardWidgetType } from '@/lib/dashboard/widgets'

interface Holding {
  stock_id: string
  name?: string
  shares: number
  cost_price: number
  current_price?: number
  current_value?: number
  pnl?: number
  pnl_pct?: number
  price_history?: number[]
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

  return { detail, listData, isLoading, isError, hasPortfolio: !!portfolioId }
}

// 各欄位差異化骨架寬度：代號 / 名稱 / 持股 / 成本價 / 現價 / 市值 / 損益(%)
const POSITION_SKELETON_WIDTHS = ['w-12', 'w-24', 'w-16', 'w-16', 'w-16', 'w-20', 'w-20']

function PositionRowSkeleton() {
  return (
    <div className="flex gap-4 px-4 py-3">
      {POSITION_SKELETON_WIDTHS.map((w, i) => (
        <Skeleton key={i} className={`h-4 ${w}`} style={{ background: 'var(--secondary)' }} />
      ))}
    </div>
  )
}

/** 表頭標籤，可選 tooltip 說明（保留原本虛線可懸停樣式） */
function HeaderLabel({ label, hint }: { label: string; hint?: string }) {
  if (!hint) return <>{label}</>
  return (
    <TooltipProvider delayDuration={150}>
      <Tooltip>
        <TooltipTrigger asChild>
          <span className="cursor-help border-b border-dotted border-[var(--border)]">
            {label}
          </span>
        </TooltipTrigger>
        <TooltipContent>{hint}</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}

/** 衍生後的持股列（含計算欄位，供排序/搜尋/匯出使用原始數值） */
interface PositionRow {
  stock_id: string
  name: string
  shares: number
  cost_price: number
  current_price: number
  market_value: number
  pnl: number
  pnl_pct: number
  price_history: number[]
}

const positionColumns: ColumnDef<PositionRow, unknown>[] = [
  {
    accessorKey: 'stock_id',
    header: () => <HeaderLabel label="代號" />,
    cell: ({ row }) => (
      <span className="font-mono font-semibold" style={{ color: 'var(--primary)' }}>
        {row.original.stock_id}
      </span>
    ),
  },
  {
    accessorKey: 'name',
    header: () => <HeaderLabel label="名稱" />,
    cell: ({ row }) => (
      <span style={{ color: 'var(--foreground)' }}>{row.original.name || '—'}</span>
    ),
  },
  {
    accessorKey: 'shares',
    header: () => <HeaderLabel label="持股(股)" />,
    cell: ({ row }) => (
      <span className="tabular-nums" style={{ color: 'var(--foreground)' }}>
        {row.original.shares.toLocaleString()}
      </span>
    ),
  },
  {
    accessorKey: 'cost_price',
    header: () => <HeaderLabel label="成本價" hint="買進時的每股平均成本（元）" />,
    cell: ({ row }) => (
      <span className="tabular-nums" style={{ color: 'var(--foreground)' }}>
        {formatPrice(row.original.cost_price)}
      </span>
    ),
  },
  {
    accessorKey: 'current_price',
    header: () => (
      <HeaderLabel label="現價" hint="目前最新成交價（元），相對成本以紅漲綠跌標示" />
    ),
    cell: ({ row }) => (
      <span
        className="tabular-nums font-semibold"
        style={{ color: getChangeColorVar(row.original.current_price - row.original.cost_price) }}
      >
        {formatPrice(row.original.current_price)}
      </span>
    ),
  },
  {
    accessorKey: 'market_value',
    header: () => <HeaderLabel label="市值" hint="目前持股的總市場價值＝現價 × 股數" />,
    cell: ({ row }) => (
      <span className="tabular-nums" style={{ color: 'var(--foreground)' }}>
        {formatCurrency(row.original.market_value)}
      </span>
    ),
  },
  {
    id: 'price_history',
    header: () => <HeaderLabel label="走勢" hint="近 30 個交易日收盤價走勢" />,
    enableSorting: false,
    cell: ({ row }) => {
      const history = row.original.price_history ?? []
      if (history.length < 2) {
        return <span style={{ color: 'var(--muted-foreground)' }}>—</span>
      }
      return <Sparkline data={history} autoColor />
    },
  },
  {
    accessorKey: 'pnl',
    header: () => (
      <HeaderLabel label="損益(%)" hint="未實現損益金額與報酬率＝（現價 − 成本）× 股數" />
    ),
    cell: ({ row }) => (
      <span
        className="tabular-nums font-semibold"
        style={{ color: getChangeColorVar(row.original.pnl) }}
      >
        {formatChange(row.original.pnl)}
        <span className="ml-1 text-xs opacity-75">({formatPercent(row.original.pnl_pct)})</span>
      </span>
    ),
  },
]

export default function DashboardPage() {
  const { detail, listData, isLoading, isError, hasPortfolio } = useDashboard()
  const {
    data: dashboardConfig,
    error: dashboardConfigError,
    mutate: mutateDashboardConfig,
  } = useSWR<DashboardConfig>('/dashboard/config', fetchAPI)
  const { data: marketSummary, error: marketSummaryError } = useSWR<MarketSummary>('/market/summary', fetchAPI)
  const { data: smartAlerts, error: smartAlertsError } = useSWR<SmartAlertsResponse>('/alerts/smart-preview?top_n=4', fetchAPI)
  const { data: rotation, error: rotationError } = useSWR<IndustryRotation>('/market/industry-rotation?top_n=4', fetchAPI)
  const { data: scoreUpgrades, error: scoreUpgradesError } = useSWR<ScoreUpgrades>('/screener/score-upgrades?days=20&top_n=4', fetchAPI)
  const [showWidgetSettings, setShowWidgetSettings] = useState(false)
  const [widgetSaving, setWidgetSaving] = useState(false)
  const [widgetActionError, setWidgetActionError] = useState('')

  const summary = detail?.summary
  const holdings = detail?.holdings ?? []
  const positionRows: PositionRow[] = holdings.map((h) => {
    const currentPrice = h.current_price ?? h.cost_price
    return {
      stock_id: h.stock_id,
      name: h.name ?? '',
      shares: h.shares,
      cost_price: h.cost_price,
      current_price: currentPrice,
      market_value: h.current_value ?? h.shares * h.cost_price,
      pnl: h.pnl ?? 0,
      pnl_pct: h.pnl_pct ?? 0,
      price_history: h.price_history ?? [],
    }
  })
  const configuredWidgets = [...(dashboardConfig?.widgets ?? [])].sort((a, b) => a.order - b.order)
  const widgets = configuredWidgets.filter((widget) => widget.enabled)

  const saveWidgetConfig = async (nextWidgets: DashboardWidget[]) => {
    setWidgetSaving(true)
    setWidgetActionError('')
    const normalized = nextWidgets.map((widget, index) => ({ ...widget, order: index + 1 }))
    try {
      const updated = await fetchAPI<DashboardConfig>('/dashboard/config', {
        method: 'PUT',
        body: JSON.stringify({ widgets: normalized }),
      })
      await mutateDashboardConfig(updated, { revalidate: false })
    } catch {
      setWidgetActionError('Widget 設定儲存失敗，原設定未變更。')
    } finally {
      setWidgetSaving(false)
    }
  }

  const toggleWidget = (id: string, enabled: boolean) => {
    void saveWidgetConfig(
      configuredWidgets.map((widget) => widget.id === id ? { ...widget, enabled } : widget)
    )
  }

  const moveWidget = (index: number, offset: -1 | 1) => {
    const target = index + offset
    if (target < 0 || target >= configuredWidgets.length) return
    const next = [...configuredWidgets]
    ;[next[index], next[target]] = [next[target], next[index]]
    void saveWidgetConfig(next)
  }

  const widgetError = (message = '資料暫時無法載入') => (
    <p className="text-sm" role="status" style={{ color: 'var(--destructive)' }}>{message}</p>
  )

  const widgetEmpty = (message: string) => (
    <p className="text-sm" style={{ color: 'var(--muted-foreground)' }}>{message}</p>
  )

  const renderWidget = (widget: DashboardWidget) => {
    if (!isSupportedDashboardWidgetType(widget.type)) {
      return widgetError('此 Widget 版本不受支援，請在管理介面停用。')
    }
    if (widget.type === 'market_summary') {
      if (marketSummaryError) return widgetError()
      if (!marketSummary) return widgetEmpty('市場資料載入中…')
      return (
        <div className="space-y-1">
          <p className="text-lg font-semibold tabular-nums" style={{ color: 'var(--foreground)' }}>
            {formatPrice(marketSummary.taiex_index)}
          </p>
          <p className="text-xs" style={{ color: getChangeColorVar(marketSummary.taiex_change) }}>
            加權指數 {formatChange(marketSummary.taiex_change)}
          </p>
          <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
            上漲 {marketSummary.up_count} · 下跌 {marketSummary.down_count}
          </p>
        </div>
      )
    }
    if (widget.type === 'portfolio_kpi') {
      if (isError && !detail) return widgetError('持倉資料暫時無法載入')
      if (isLoading) return widgetEmpty('持倉資料載入中…')
      if (!summary) return widgetEmpty('尚未建立投資組合')
      return (
        <div className="space-y-1">
          <p className="text-lg font-semibold tabular-nums" style={{ color: 'var(--foreground)' }}>
            {formatCurrency(summary.total_value)}
          </p>
          <p className="text-xs" style={{ color: getChangeColorVar(summary.total_pnl) }}>
            損益 {formatChange(summary.total_pnl)}（{formatPercent(summary.total_pnl_pct)}）
          </p>
          <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>{holdings.length} 檔持股</p>
        </div>
      )
    }
    if (widget.type === 'smart_alerts') {
      if (smartAlertsError) return widgetError()
      if (!smartAlerts) return widgetEmpty('智慧警報載入中…')
      if (!smartAlerts.alerts.length) return widgetEmpty('目前沒有智慧警報')
      return (
        <div className="space-y-1">
          {smartAlerts.alerts.slice(0, 3).map((item) => (
            <p key={item.stock_id} className="text-sm truncate" style={{ color: 'var(--foreground)' }}>
              {item.stock_id} {item.reasons[0]}
            </p>
          ))}
        </div>
      )
    }
    if (widget.type === 'industry_rotation') {
      if (rotationError) return widgetError()
      if (!rotation) return widgetEmpty('產業輪動載入中…')
      if (!rotation.industries.length) return widgetEmpty('目前沒有產業輪動資料')
      return (
        <div className="space-y-1">
          {rotation.industries.slice(0, 3).map((item) => (
            <p key={item.industry} className="text-sm flex justify-between gap-2" style={{ color: 'var(--foreground)' }}>
              <span className="truncate">{item.industry}</span>
              <span style={{ color: getChangeColorVar(item.rotation_score) }}>{item.quadrant}</span>
            </p>
          ))}
        </div>
      )
    }
    if (scoreUpgradesError) return widgetError()
    if (!scoreUpgrades) return widgetEmpty('評分升降級載入中…')
    if (!scoreUpgrades.upgrades.length) return widgetEmpty('目前沒有評分升級資料')
    return (
      <div className="space-y-1">
        {scoreUpgrades.upgrades.slice(0, 3).map((item) => (
          <p key={item.stock_id} className="text-sm flex justify-between gap-2" style={{ color: 'var(--foreground)' }}>
            <span>{item.stock_id}</span>
            <span style={{ color: getChangeColorVar(item.score_change ?? 0) }}>
              {item.score_change != null && item.score_change > 0 ? '+' : ''}{item.score_change?.toFixed(1) ?? '—'}
            </span>
          </p>
        ))}
      </div>
    )
  }

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

      {isError && !detail && !listData && (
        <EmptyState
          title="無法載入持倉資料"
          description="請確認後端服務是否正常運行，或稍後再試"
          icon="!"
        />
      )}

      {(!isError || detail || listData) && (
        <>
          {isError && (detail || listData) && <StaleBanner />}
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

          {(configuredWidgets.length > 0 || dashboardConfigError) && (
            <div
              className="rounded-lg p-4 mb-6"
              style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
            >
              <div className="flex items-center justify-between mb-3">
                <div>
                  <h2 className="text-sm font-semibold" style={{ color: 'var(--foreground)' }}>自訂 Dashboard</h2>
                  <p className="text-xs mt-0.5" style={{ color: 'var(--muted-foreground)' }}>
                    選擇、排序並保存你的首頁資訊卡
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>{widgets.length} 個啟用</span>
                  <button
                    type="button"
                    onClick={() => setShowWidgetSettings((value) => !value)}
                    className="text-xs font-medium"
                    style={{ color: 'var(--primary)' }}
                  >
                    {showWidgetSettings ? '完成' : '管理 Widget'}
                  </button>
                </div>
              </div>
              {dashboardConfigError && widgetError('Widget 設定載入失敗，請稍後重試。')}
              {widgetActionError && widgetError(widgetActionError)}
              {showWidgetSettings && configuredWidgets.length > 0 && (
                <div className="mb-4 space-y-2 rounded-md p-3" style={{ background: 'var(--secondary)' }}>
                  {configuredWidgets.map((widget, index) => (
                    <div key={widget.id} className="flex items-center gap-2">
                      <Switch
                        checked={widget.enabled}
                        onCheckedChange={(enabled) => toggleWidget(widget.id, enabled)}
                        disabled={widgetSaving}
                        aria-label={`切換 ${widget.title}`}
                      />
                      <span className="flex-1 text-sm" style={{ color: 'var(--foreground)' }}>{widget.title}</span>
                      <button
                        type="button"
                        disabled={widgetSaving || index === 0}
                        onClick={() => moveWidget(index, -1)}
                        className="h-7 px-2 text-xs disabled:opacity-40"
                        aria-label={`上移 ${widget.title}`}
                        style={{ color: 'var(--muted-foreground)' }}
                      >
                        ↑
                      </button>
                      <button
                        type="button"
                        disabled={widgetSaving || index === configuredWidgets.length - 1}
                        onClick={() => moveWidget(index, 1)}
                        className="h-7 px-2 text-xs disabled:opacity-40"
                        aria-label={`下移 ${widget.title}`}
                        style={{ color: 'var(--muted-foreground)' }}
                      >
                        ↓
                      </button>
                    </div>
                  ))}
                </div>
              )}
              <div className="grid md:grid-cols-3 gap-3">
                {widgets.slice(0, 6).map((widget) => (
                  <div key={widget.id} className="rounded-md p-3" style={{ background: 'var(--secondary)' }}>
                    <p className="text-xs mb-2" style={{ color: 'var(--muted-foreground)' }}>{widget.title}</p>
                    {renderWidget(widget)}
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
            <div className="p-4">
              {isLoading ? (
                <div className="space-y-1">
                  {[...Array(5)].map((_, i) => (
                    <PositionRowSkeleton key={i} />
                  ))}
                </div>
              ) : positionRows.length > 0 ? (
                <DataTable
                  columns={positionColumns}
                  data={positionRows}
                  searchable
                  searchPlaceholder="搜尋代號 / 名稱..."
                  exportable
                  exportFilename="持股明細"
                  pageSize={20}
                />
              ) : (
                <EmptyState
                  title={hasPortfolio ? '目前沒有持股' : '尚未建立投資組合'}
                  description={hasPortfolio ? '尚未建立任何持倉紀錄' : '請前往投資組合頁面新增持股'}
                  icon="+"
                />
              )}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
