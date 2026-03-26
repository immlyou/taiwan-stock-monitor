'use client'

import useSWR from 'swr'
import { fetchAPI } from '@/lib/api/client'
import { EmptyState } from '@/components/shared/EmptyState'
import { Skeleton } from '@/components/ui/skeleton'
import { formatPercent, getChangeColorVar } from '@/lib/utils/format'
import {
  Treemap,
  ResponsiveContainer,
  Tooltip,
} from 'recharts'

// 對應 GET /market/heatmap
interface HeatmapStock {
  stock_id: string
  name: string
  price?: number
  change_pct: number
}

interface HeatmapIndustry {
  industry: string
  stocks: HeatmapStock[]
}

interface HeatmapData {
  date: string
  industries: HeatmapIndustry[]
}

function useHeatmap() {
  const { data, error, isLoading } = useSWR<HeatmapData>(
    '/market/heatmap',
    (path: string) => fetchAPI<HeatmapData>(path),
    { refreshInterval: 60000, revalidateOnFocus: true }
  )
  return { data, isLoading, isError: !!error }
}

function changeToColor(changePercent: number): string {
  if (changePercent >= 5) return '#b91c1c'
  if (changePercent >= 3) return '#dc2626'
  if (changePercent >= 1) return '#ef4444'
  if (changePercent > 0) return '#fca5a5'
  if (changePercent === 0) return '#475569'
  if (changePercent >= -1) return '#86efac'
  if (changePercent >= -3) return '#22c55e'
  if (changePercent >= -5) return '#16a34a'
  return '#15803d'
}

interface TreemapEntry {
  name: string
  stock_id: string
  size: number
  change_pct: number
  fill: string
  [key: string]: unknown
}

interface CustomContentProps {
  x?: number
  y?: number
  width?: number
  height?: number
  name?: string
  stock_id?: string
  change_pct?: number
}

function CustomContent(props: CustomContentProps) {
  const { x = 0, y = 0, width = 0, height = 0, name, stock_id, change_pct = 0 } = props
  const showText = width > 50 && height > 40
  const showSubText = width > 70 && height > 60
  return (
    <g>
      <rect
        x={x + 1}
        y={y + 1}
        width={width - 2}
        height={height - 2}
        style={{ fill: changeToColor(change_pct), stroke: 'var(--background)', strokeWidth: 1 }}
        rx={2}
      />
      {showText && (
        <text
          x={x + width / 2}
          y={y + height / 2 - (showSubText ? 8 : 0)}
          textAnchor="middle"
          dominantBaseline="middle"
          style={{ fill: '#fff', fontSize: 12, fontWeight: 600 }}
        >
          {stock_id}
        </text>
      )}
      {showSubText && (
        <>
          {name && (
            <text
              x={x + width / 2}
              y={y + height / 2 + 6}
              textAnchor="middle"
              dominantBaseline="middle"
              style={{ fill: '#ffffffcc', fontSize: 9 }}
            >
              {name}
            </text>
          )}
          <text
            x={x + width / 2}
            y={y + height / 2 + 20}
            textAnchor="middle"
            dominantBaseline="middle"
            style={{ fill: '#ffffffcc', fontSize: 10 }}
          >
            {formatPercent(change_pct)}
          </text>
        </>
      )}
    </g>
  )
}

interface TooltipPayload {
  payload?: TreemapEntry
}

function CustomTooltip({ active, payload }: { active?: boolean; payload?: TooltipPayload[] }) {
  if (!active || !payload?.length) return null
  const item = payload[0]?.payload
  if (!item) return null
  return (
    <div
      className="rounded-lg p-3 text-sm shadow-lg"
      style={{ background: 'var(--card)', border: '1px solid var(--border)', minWidth: 150 }}
    >
      <p className="font-semibold" style={{ color: 'var(--foreground)' }}>
        {item.stock_id} {item.name}
      </p>
      <p
        className="mt-1 tabular-nums font-semibold"
        style={{ color: getChangeColorVar(item.change_pct) }}
      >
        {formatPercent(item.change_pct)}
      </p>
    </div>
  )
}

const LEGEND_ITEMS = [
  { label: '+5% 以上', color: '#b91c1c' },
  { label: '+3~5%', color: '#ef4444' },
  { label: '0~3%', color: '#fca5a5' },
  { label: '持平', color: '#475569' },
  { label: '-3~0%', color: '#86efac' },
  { label: '-5~-3%', color: '#22c55e' },
  { label: '-5% 以下', color: '#15803d' },
]

export default function HeatmapPage() {
  const { data, isLoading, isError } = useHeatmap()

  // 把 industries[].stocks[] 攤平，用 price 近似市值作為方塊大小
  // 取前 200 大股票避免小型股過多導致 Treemap 擁擠
  const allStocks = (data?.industries ?? []).flatMap((industry) =>
    (industry.stocks ?? []).map((stock) => ({
      ...stock,
      industry: industry.industry,
    }))
  )
  // 按 price 降序取前 200
  allStocks.sort((a, b) => (b.price ?? 0) - (a.price ?? 0))
  const topStocks = allStocks.slice(0, 200)

  const treeData: TreemapEntry[] = topStocks.map((stock) => ({
    name: stock.name,
    stock_id: stock.stock_id,
    size: Math.max(stock.price ?? 1, 1),
    change_pct: stock.change_pct,
    fill: changeToColor(stock.change_pct),
  }))

  return (
    <div>
      {/* 頁面標題 */}
      <div className="mb-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold" style={{ color: 'var(--foreground)' }}>
              市場熱力圖
            </h1>
            <p className="text-sm mt-1" style={{ color: 'var(--muted-foreground)' }}>
              顏色代表漲跌幅（紅漲綠跌）
            </p>
          </div>
          {data?.date && (
            <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
              資料日期：{data.date}
            </span>
          )}
        </div>
      </div>

      {/* 圖例 */}
      <div className="flex flex-wrap gap-3 mb-4">
        {LEGEND_ITEMS.map((item) => (
          <div key={item.label} className="flex items-center gap-1.5">
            <span
              className="w-3 h-3 rounded-sm inline-block"
              style={{ background: item.color }}
            />
            <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
              {item.label}
            </span>
          </div>
        ))}
      </div>

      {/* 熱力圖 */}
      <div
        className="rounded-lg overflow-hidden"
        style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
      >
        {isLoading ? (
          <div className="p-6 grid grid-cols-4 md:grid-cols-6 gap-2" style={{ minHeight: 480 }}>
            {[...Array(24)].map((_, i) => (
              <Skeleton
                key={i}
                style={{
                  background: 'var(--secondary)',
                  height: `${60 + Math.random() * 80}px`,
                  borderRadius: 4,
                }}
              />
            ))}
          </div>
        ) : isError ? (
          <EmptyState
            title="無法載入熱力圖"
            description="請確認後端服務是否正常運行，或稍後再試"
            icon="!"
          />
        ) : treeData.length === 0 ? (
          <EmptyState title="暫無熱力圖資料" icon="+" />
        ) : (
          <div style={{ height: 'calc(100vh - 200px)', minHeight: 600 }}>
            <ResponsiveContainer width="100%" height="100%">
              <Treemap
                data={treeData}
                dataKey="size"
                content={<CustomContent />}
              >
                <Tooltip content={<CustomTooltip />} />
              </Treemap>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* 統計摘要 */}
      {!isLoading && treeData.length > 0 && (
        <p className="mt-3 text-xs" style={{ color: 'var(--muted-foreground)' }}>
          顯示前 200 大股票，共 {data?.industries?.length ?? 0} 個產業
        </p>
      )}
    </div>
  )
}
