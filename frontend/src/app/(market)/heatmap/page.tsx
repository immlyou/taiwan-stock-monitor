'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import useSWR from 'swr'
import { fetchAPI } from '@/lib/api/client'
import { EmptyState } from '@/components/shared/EmptyState'
import { Skeleton } from '@/components/ui/skeleton'
import { formatPercent, formatPrice } from '@/lib/utils/format'

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

interface HeatmapStock {
  stock_id: string
  name: string
  price: number
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

interface ProcessedIndustry {
  industry: string
  weight: number
  stocks: HeatmapStock[]
}

interface TooltipInfo {
  stock: HeatmapStock
  industry: string
  x: number
  y: number
}

/* ------------------------------------------------------------------ */
/*  Data hook                                                          */
/* ------------------------------------------------------------------ */

function useHeatmap() {
  const { data, error, isLoading } = useSWR<HeatmapData>(
    '/market/heatmap',
    (path: string) => fetchAPI<HeatmapData>(path),
    { refreshInterval: 60000, revalidateOnFocus: true },
  )
  return { data, isLoading, isError: !!error }
}

/* ------------------------------------------------------------------ */
/*  Color scale (Bloomberg-style multi-stop gradient)                  */
/* ------------------------------------------------------------------ */

function getHeatColor(changePct: number): string {
  if (changePct >= 7) return '#7f1d1d'
  if (changePct >= 5) return '#991b1b'
  if (changePct >= 3) return '#b91c1c'
  if (changePct >= 1) return '#dc2626'
  if (changePct > 0) return '#ef4444'
  if (changePct === 0) return '#374151'
  if (changePct > -1) return '#22c55e'
  if (changePct > -3) return '#16a34a'
  if (changePct > -5) return '#15803d'
  return '#14532d'
}

/* ------------------------------------------------------------------ */
/*  Data processing: group by industry, cap at 150 stocks              */
/* ------------------------------------------------------------------ */

function processIndustries(data: HeatmapData | undefined): ProcessedIndustry[] {
  if (!data?.industries?.length) return []

  // Flatten all stocks with their industry tag
  const tagged = data.industries.flatMap((ind) =>
    (ind.stocks ?? []).map((s) => ({ ...s, industry: ind.industry })),
  )

  // Sort by price descending, take top 150
  tagged.sort((a, b) => (b.price ?? 0) - (a.price ?? 0))
  const top = tagged.slice(0, 150)

  // Re-group by industry, preserving original order
  const industryOrder: string[] = []
  const map = new Map<string, HeatmapStock[]>()
  for (const s of top) {
    if (!map.has(s.industry)) {
      industryOrder.push(s.industry)
      map.set(s.industry, [])
    }
    map.get(s.industry)!.push(s)
  }

  return industryOrder.map((ind) => {
    const stocks = map.get(ind)!
    const weight = stocks.reduce((sum, s) => sum + (s.price ?? 1), 0)
    return { industry: ind, weight, stocks }
  })
}

/* ------------------------------------------------------------------ */
/*  Legend                                                              */
/* ------------------------------------------------------------------ */

const LEGEND_ITEMS = [
  { label: '+7%+', color: '#7f1d1d' },
  { label: '+5%', color: '#991b1b' },
  { label: '+3%', color: '#b91c1c' },
  { label: '+1%', color: '#dc2626' },
  { label: '0~1%', color: '#ef4444' },
  { label: '0%', color: '#374151' },
  { label: '-1%', color: '#22c55e' },
  { label: '-3%', color: '#16a34a' },
  { label: '-5%', color: '#15803d' },
  { label: '-5%-', color: '#14532d' },
]

/* ------------------------------------------------------------------ */
/*  Tooltip component (fixed position, follows cursor)                 */
/* ------------------------------------------------------------------ */

function HeatmapTooltip({ info }: { info: TooltipInfo | null }) {
  if (!info) return null
  const { stock, industry, x, y } = info

  // Offset so tooltip doesn't overlap cursor
  const offsetX = 14
  const offsetY = 14

  return (
    <div
      style={{
        position: 'fixed',
        left: x + offsetX,
        top: y + offsetY,
        zIndex: 9999,
        pointerEvents: 'none',
        background: '#1e1e2e',
        border: '1px solid #444',
        borderRadius: 8,
        padding: '10px 14px',
        minWidth: 180,
        boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, marginBottom: 4 }}>
        <span style={{ color: '#fff', fontWeight: 700, fontSize: 14 }}>
          {stock.stock_id}
        </span>
        <span style={{ color: '#aaa', fontSize: 12 }}>{stock.name}</span>
      </div>
      <div style={{ color: '#ccc', fontSize: 11, marginBottom: 6 }}>{industry}</div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ color: '#fff', fontSize: 14, fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>
          ${formatPrice(stock.price)}
        </span>
        <span
          style={{
            color: getHeatColor(stock.change_pct),
            fontSize: 14,
            fontWeight: 700,
            fontVariantNumeric: 'tabular-nums',
            filter: 'brightness(1.5)',
          }}
        >
          {formatPercent(stock.change_pct)}
        </span>
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Single stock cell                                                  */
/* ------------------------------------------------------------------ */

interface StockCellProps {
  stock: HeatmapStock
  industry: string
  index: number
  onHover: (info: TooltipInfo | null) => void
}

function StockCell({ stock, industry, index, onHover }: StockCellProps) {
  const ref = useRef<HTMLDivElement>(null)
  const [entered, setEntered] = useState(false)

  // Staggered entrance animation
  useEffect(() => {
    const timer = setTimeout(() => setEntered(true), index * 5)
    return () => clearTimeout(timer)
  }, [index])

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      onHover({ stock, industry, x: e.clientX, y: e.clientY })
    },
    [stock, industry, onHover],
  )

  const handleMouseLeave = useCallback(() => {
    onHover(null)
  }, [onHover])

  const bg = getHeatColor(stock.change_pct)

  return (
    <div
      ref={ref}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      style={{
        flex: `${stock.price} 1 0`,
        minWidth: 0,
        minHeight: 40,
        backgroundColor: bg,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        border: '1px solid rgba(0,0,0,0.25)',
        cursor: 'pointer',
        overflow: 'hidden',
        padding: '2px 4px',
        transition: 'transform 0.15s ease, box-shadow 0.15s ease, background-color 0.5s ease',
        opacity: entered ? 1 : 0,
        transform: entered ? 'scale(1)' : 'scale(0.85)',
        position: 'relative',
      }}
      className="stock-cell"
    >
      <span
        style={{
          color: '#fff',
          fontSize: 11,
          fontWeight: 700,
          lineHeight: 1.2,
          textShadow: '0 1px 3px rgba(0,0,0,0.6)',
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          maxWidth: '100%',
        }}
      >
        {stock.stock_id}
      </span>
      <span
        style={{
          color: 'rgba(255,255,255,0.85)',
          fontSize: 9,
          fontWeight: 500,
          lineHeight: 1.2,
          textShadow: '0 1px 2px rgba(0,0,0,0.5)',
          fontVariantNumeric: 'tabular-nums',
          whiteSpace: 'nowrap',
        }}
      >
        {formatPercent(stock.change_pct)}
      </span>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Industry group                                                     */
/* ------------------------------------------------------------------ */

interface IndustryGroupProps {
  industry: ProcessedIndustry
  startIndex: number
  onHover: (info: TooltipInfo | null) => void
}

function IndustryGroup({ industry, startIndex, onHover }: IndustryGroupProps) {
  return (
    <div
      style={{
        flex: `${industry.weight} 1 0`,
        minWidth: 0,
        display: 'flex',
        flexDirection: 'column',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      {/* Industry label */}
      <div
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          zIndex: 5,
          background: 'rgba(0,0,0,0.55)',
          backdropFilter: 'blur(4px)',
          padding: '2px 8px',
          borderBottomRightRadius: 6,
          pointerEvents: 'none',
        }}
      >
        <span style={{ color: 'rgba(255,255,255,0.85)', fontSize: 10, fontWeight: 600 }}>
          {industry.industry}
        </span>
      </div>

      {/* Stock cells inside industry */}
      <div
        style={{
          flex: 1,
          display: 'flex',
          flexWrap: 'wrap',
          alignContent: 'stretch',
        }}
      >
        {industry.stocks.map((stock, i) => (
          <StockCell
            key={stock.stock_id}
            stock={stock}
            industry={industry.industry}
            index={startIndex + i}
            onHover={onHover}
          />
        ))}
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Loading skeleton                                                   */
/* ------------------------------------------------------------------ */

function HeatmapSkeleton() {
  return (
    <div
      style={{
        height: 'calc(100vh - 120px)',
        minHeight: 500,
        display: 'flex',
        flexWrap: 'wrap',
        gap: 2,
        padding: 2,
      }}
    >
      {Array.from({ length: 30 }).map((_, i) => (
        <Skeleton
          key={i}
          style={{
            flex: `${50 + Math.random() * 150} 1 0`,
            minHeight: 50 + Math.random() * 60,
            background: 'var(--secondary)',
            borderRadius: 2,
          }}
        />
      ))}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Main page                                                          */
/* ------------------------------------------------------------------ */

export default function HeatmapPage() {
  const { data, isLoading, isError } = useHeatmap()
  const [tooltip, setTooltip] = useState<TooltipInfo | null>(null)

  const industries = useMemo(() => processIndustries(data), [data])
  const totalStocks = useMemo(
    () => industries.reduce((sum, ind) => sum + ind.stocks.length, 0),
    [industries],
  )

  // Calculate cumulative start index for staggered animation
  const startIndices = useMemo(() => {
    const indices: number[] = []
    let acc = 0
    for (const ind of industries) {
      indices.push(acc)
      acc += ind.stocks.length
    }
    return indices
  }, [industries])

  const handleHover = useCallback((info: TooltipInfo | null) => {
    setTooltip(info)
  }, [])

  return (
    <div style={{ position: 'relative' }}>
      {/* ---- Header bar ---- */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: 8,
          flexWrap: 'wrap',
          gap: 8,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 12 }}>
          <h1 style={{ color: 'var(--foreground)', fontSize: 18, fontWeight: 700, margin: 0 }}>
            Market Heatmap
          </h1>
          {data?.date && (
            <span style={{ color: 'var(--muted-foreground)', fontSize: 11 }}>
              {data.date}
            </span>
          )}
          {!isLoading && totalStocks > 0 && (
            <span style={{ color: 'var(--muted-foreground)', fontSize: 11 }}>
              {totalStocks} stocks / {industries.length} industries
            </span>
          )}
        </div>

        {/* Legend */}
        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', alignItems: 'center' }}>
          {LEGEND_ITEMS.map((item) => (
            <div key={item.label} style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
              <span
                style={{
                  width: 10,
                  height: 10,
                  borderRadius: 2,
                  background: item.color,
                  display: 'inline-block',
                  flexShrink: 0,
                }}
              />
              <span style={{ color: 'var(--muted-foreground)', fontSize: 10 }}>
                {item.label}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* ---- Main heatmap area ---- */}
      {isLoading ? (
        <HeatmapSkeleton />
      ) : isError ? (
        <div
          style={{
            height: 'calc(100vh - 120px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <EmptyState
            title="Unable to load heatmap"
            description="Please check if the backend service is running, or try again later"
            icon="!"
          />
        </div>
      ) : industries.length === 0 ? (
        <div
          style={{
            height: 'calc(100vh - 120px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <EmptyState title="No heatmap data available" icon="+" />
        </div>
      ) : (
        <div
          style={{
            height: 'calc(100vh - 120px)',
            minHeight: 500,
            display: 'flex',
            flexWrap: 'wrap',
            gap: 2,
            borderRadius: 6,
            overflow: 'hidden',
            background: '#111',
          }}
        >
          {industries.map((industry, idx) => (
            <IndustryGroup
              key={industry.industry}
              industry={industry}
              startIndex={startIndices[idx]}
              onHover={handleHover}
            />
          ))}
        </div>
      )}

      {/* ---- Tooltip ---- */}
      <HeatmapTooltip info={tooltip} />

      {/* ---- Global hover style ---- */}
      <style>{`
        .stock-cell:hover {
          transform: scale(1.08) !important;
          z-index: 10 !important;
          border-color: rgba(255,255,255,0.6) !important;
          box-shadow: 0 0 12px rgba(255,255,255,0.3) !important;
        }
      `}</style>
    </div>
  )
}
