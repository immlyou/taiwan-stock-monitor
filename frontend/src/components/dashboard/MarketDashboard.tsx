'use client'

import { useMarketSummary } from '@/lib/hooks/useMarketSummary'
import { KpiCard } from '@/components/shared/KpiCard'
import { EmptyState } from '@/components/shared/EmptyState'
import { formatCurrency, formatPercent, formatChange, formatVolumeValue } from '@/lib/utils/format'

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

  const kpiCards = [
    {
      title: '加權指數',
      value: isLoading ? '-' : formatCurrency(summary?.taiex?.close ?? 0),
      change: summary?.taiex?.change,
      changeLabel: formatPercent(summary?.taiex?.changePercent ?? 0),
      accentColor: summary?.taiex?.change !== undefined
        ? summary.taiex.change > 0
          ? 'var(--stock-up)'
          : summary.taiex.change < 0
            ? 'var(--stock-down)'
            : 'var(--border)'
        : 'var(--primary)',
    },
    {
      title: '漲跌點數',
      value: isLoading
        ? '-'
        : formatChange(summary?.taiex?.change ?? 0),
      subValue: isLoading ? undefined : formatPercent(summary?.taiex?.changePercent ?? 0),
      accentColor: 'var(--primary)',
    },
    {
      title: '成交量（億元）',
      value: isLoading
        ? '-'
        : formatVolumeValue(summary?.taiex?.volumeValue ?? 0),
      accentColor: 'var(--primary)',
    },
    {
      title: '上漲家數',
      value: isLoading ? '-' : String(summary?.advances ?? 0),
      accentColor: 'var(--stock-up)',
    },
    {
      title: '下跌家數',
      value: isLoading ? '-' : String(summary?.declines ?? 0),
      accentColor: 'var(--stock-down)',
    },
    {
      title: '外資買賣超',
      value: isLoading
        ? '-'
        : formatVolumeValue(summary?.foreignNet ?? 0),
      change: summary?.foreignNet,
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
                value={summary?.advances ?? 0}
                total={(summary?.advances ?? 0) + (summary?.declines ?? 0) + (summary?.unchanged ?? 0)}
                color="var(--stock-up)"
              />
              <MarketStatRow
                label="下跌"
                value={summary?.declines ?? 0}
                total={(summary?.advances ?? 0) + (summary?.declines ?? 0) + (summary?.unchanged ?? 0)}
                color="var(--stock-down)"
              />
              <MarketStatRow
                label="平盤"
                value={summary?.unchanged ?? 0}
                total={(summary?.advances ?? 0) + (summary?.declines ?? 0) + (summary?.unchanged ?? 0)}
                color="var(--stock-flat)"
              />
            </div>
          )}
        </div>

        {/* 三大法人買賣超 */}
        <div
          className="rounded-lg p-4"
          style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
        >
          <h3 className="text-sm font-semibold mb-4" style={{ color: 'var(--foreground)' }}>
            三大法人買賣超
          </h3>
          {isLoading ? (
            <div className="space-y-2">
              {[...Array(3)].map((_, i) => (
                <div key={i} className="h-6 rounded" style={{ background: 'var(--secondary)' }} />
              ))}
            </div>
          ) : (
            <div className="space-y-3">
              <InstitutionalRow label="外資" value={summary?.foreignNet ?? 0} />
              <InstitutionalRow label="投信" value={summary?.investmentTrustNet ?? 0} />
              <InstitutionalRow label="自營商" value={summary?.dealerNet ?? 0} />
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

function InstitutionalRow({ label, value }: { label: string; value: number }) {
  const color =
    value > 0 ? 'var(--stock-up)' : value < 0 ? 'var(--stock-down)' : 'var(--stock-flat)'
  return (
    <div className="flex justify-between items-center">
      <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
        {label}
      </span>
      <span className="text-xs font-semibold tabular-nums" style={{ color }}>
        {value > 0 ? '+' : ''}{formatVolumeValue(value)}
      </span>
    </div>
  )
}
