'use client'

import { useMarketSummary } from '@/lib/hooks/useMarketSummary'
import { KpiCard } from '@/components/shared/KpiCard'
import { EmptyState } from '@/components/shared/EmptyState'
import { formatCurrency, formatPercent, formatChange } from '@/lib/utils/format'

export function MarketDashboard() {
  const { summary, isLoading, isError } = useMarketSummary()

  if (isError) {
    return (
      <EmptyState
        title="無法載入市場資料"
        description="請確認後端服務是否正常運行，或稍後再試"
        icon="⚠️"
      />
    )
  }

  // taiex_change 是點數變化，計算漲跌幅百分比
  const taiexIndex = summary?.taiex_index ?? 0
  const taiexChange = summary?.taiex_change ?? 0
  // 從現值和變動點反推前一天收盤：prev = index - change
  const taiexChangePct = taiexIndex > 0 && taiexChange !== 0
    ? (taiexChange / (taiexIndex - taiexChange)) * 100
    : 0

  const kpiCards = [
    {
      title: '加權指數',
      value: isLoading ? '-' : formatCurrency(taiexIndex),
      change: taiexChange,
      changeLabel: formatPercent(taiexChangePct),
      accentColor: taiexChange > 0
        ? 'var(--stock-up)'
        : taiexChange < 0
          ? 'var(--stock-down)'
          : 'var(--border)',
    },
    {
      title: '漲跌點數',
      value: isLoading ? '-' : formatChange(taiexChange),
      subValue: isLoading ? undefined : formatPercent(taiexChangePct),
      accentColor: 'var(--primary)',
    },
    {
      title: '總家數',
      value: isLoading ? '-' : String(summary?.total_stocks ?? 0),
      accentColor: 'var(--primary)',
    },
    {
      title: '上漲家數',
      value: isLoading ? '-' : String(summary?.up_count ?? 0),
      accentColor: 'var(--stock-up)',
    },
    {
      title: '下跌家數',
      value: isLoading ? '-' : String(summary?.down_count ?? 0),
      accentColor: 'var(--stock-down)',
    },
    {
      title: '平盤家數',
      value: isLoading ? '-' : String(summary?.flat_count ?? 0),
      accentColor: 'var(--primary)',
    },
  ]

  return (
    <div>
      {/* KPI 卡片區 */}
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-4 mb-8">
        {kpiCards.map((card) => (
          <KpiCard
            key={card.title}
            title={card.title}
            value={card.value}
            subValue={card.subValue}
            change={card.change}
            changeLabel={card.changeLabel}
            accentColor={card.accentColor}
            isLoading={isLoading}
          />
        ))}
      </div>

      {/* 市場統計概覽 */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* 漲跌家數統計 */}
        <div
          className="rounded-lg p-4"
          style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
        >
          <h3 className="text-sm font-semibold mb-4" style={{ color: 'var(--foreground)' }}>
            漲跌統計
          </h3>
          {isLoading ? (
            <div className="space-y-2">
              {[...Array(3)].map((_, i) => (
                <div key={i} className="h-6 rounded" style={{ background: 'var(--secondary)' }} />
              ))}
            </div>
          ) : (
            <div className="space-y-3">
              <MarketStatRow
                label="上漲"
                value={summary?.up_count ?? 0}
                total={(summary?.up_count ?? 0) + (summary?.down_count ?? 0) + (summary?.flat_count ?? 0)}
                color="var(--stock-up)"
              />
              <MarketStatRow
                label="下跌"
                value={summary?.down_count ?? 0}
                total={(summary?.up_count ?? 0) + (summary?.down_count ?? 0) + (summary?.flat_count ?? 0)}
                color="var(--stock-down)"
              />
              <MarketStatRow
                label="平盤"
                value={summary?.flat_count ?? 0}
                total={(summary?.up_count ?? 0) + (summary?.down_count ?? 0) + (summary?.flat_count ?? 0)}
                color="var(--stock-flat)"
              />
            </div>
          )}
        </div>

        {/* 今日強勢股 */}
        <div
          className="rounded-lg p-4"
          style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
        >
          <h3 className="text-sm font-semibold mb-4" style={{ color: 'var(--foreground)' }}>
            今日漲幅前五
          </h3>
          {isLoading ? (
            <div className="space-y-2">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="h-5 rounded" style={{ background: 'var(--secondary)' }} />
              ))}
            </div>
          ) : (
            <div className="space-y-2">
              {(summary?.top_gainers ?? []).slice(0, 5).map((item) => (
                <div key={item.stock_id} className="flex justify-between items-center">
                  <span className="text-xs font-mono" style={{ color: 'var(--primary)' }}>
                    {item.stock_id}
                  </span>
                  <span className="text-xs font-semibold" style={{ color: 'var(--stock-up)' }}>
                    +{item.change_pct.toFixed(2)}%
                  </span>
                </div>
              ))}
              {!summary?.top_gainers?.length && (
                <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>暫無資料</p>
              )}
            </div>
          )}
        </div>

        {/* 資料說明 */}
        <div
          className="rounded-lg p-4"
          style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
        >
          <h3 className="text-sm font-semibold mb-4" style={{ color: 'var(--foreground)' }}>
            資料說明
          </h3>
          <div className="space-y-2 text-xs" style={{ color: 'var(--muted-foreground)' }}>
            <p>資料來源：台灣證券交易所</p>
            <p>更新頻率：每 30 秒自動更新</p>
            <p>漲跌顏色：漲紅跌綠（台股慣例）</p>
            <p>成交量單位：張（1,000 股）</p>
            {summary?.date && <p>資料日期：{summary.date}</p>}
          </div>
        </div>
      </div>
    </div>
  )
}

function MarketStatRow({
  label,
  value,
  total,
  color,
}: {
  label: string
  value: number
  total: number
  color: string
}) {
  const percent = total > 0 ? (value / total) * 100 : 0
  return (
    <div>
      <div className="flex justify-between mb-1">
        <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
          {label}
        </span>
        <span className="text-xs font-semibold" style={{ color }}>
          {value} 家
        </span>
      </div>
      <div className="h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--secondary)' }}>
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${percent}%`, background: color }}
        />
      </div>
    </div>
  )
}
