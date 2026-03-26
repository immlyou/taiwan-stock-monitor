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

interface HeatmapItem {
  code: string
  name: string
  marketCap: number
  changePercent: number
  sector: string
}

interface HeatmapData {
  items: HeatmapItem[]
  updatedAt: string
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
  code: string
  size: number
  changePercent: number
  fill: string
  [key: string]: unknown
}

interface CustomContentProps {
  x?: number
  y?: number
  width?: number
  height?: number
  name?: string
  code?: string
  changePercent?: number
}

function CustomContent(props: CustomContentProps) {
  const { x = 0, y = 0, width = 0, height = 0, name, code, changePercent = 0 } = props
  const showText = width > 50 && height > 40
  const showSubText = width > 70 && height > 60
  return (
    <g>
      <rect
        x={x + 1}
        y={y + 1}
        width={width - 2}
        height={height - 2}
        style={{ fill: changeToColor(changePercent), stroke: 'var(--background)', strokeWidth: 1 }}
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
          {code}
        </text>
      )}
      {showSubText && (
        <text
          x={x + width / 2}
          y={y + height / 2 + 10}
          textAnchor="middle"
          dominantBaseline="middle"
          style={{ fill: '#ffffffcc', fontSize: 10 }}
        >
          {formatPercent(changePercent)}
        </text>
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
        {item.code} {item.name}
      </p>
      <p
        className="mt-1 tabular-nums font-semibold"
        style={{ color: getChangeColorVar(item.changePercent) }}
      >
        {formatPercent(item.changePercent)}
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

  const treeData: TreemapEntry[] = (data?.items ?? []).map((item) => ({
    name: item.name,
    code: item.code,
    size: item.marketCap,
    changePercent: item.changePercent,
    fill: changeToColor(item.changePercent),
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
              方塊大小代表市值，顏色代表漲跌幅（紅漲綠跌）
            </p>
          </div>
          {data?.updatedAt && (
            <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
              更新：{new Date(data.updatedAt).toLocaleTimeString('zh-TW')}
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
          <div style={{ height: 560 }}>
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
    </div>
  )
}
