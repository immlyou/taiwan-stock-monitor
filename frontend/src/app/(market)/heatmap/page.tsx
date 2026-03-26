'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import useSWR from 'swr'
import { fetchAPI } from '@/lib/api/client'
import { EmptyState } from '@/components/shared/EmptyState'
import { Skeleton } from '@/components/ui/skeleton'
import { formatPercent } from '@/lib/utils/format'

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
  avgChange: number
  stockCount: number
  upCount: number
  downCount: number
  stocks: HeatmapStock[]
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
/*  Color helpers                                                      */
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

function getTextColor(changePct: number): string {
  return changePct >= 0 ? '#fca5a5' : '#86efac'
}

/* ------------------------------------------------------------------ */
/*  Process data                                                       */
/* ------------------------------------------------------------------ */

function processIndustries(data: HeatmapData | undefined): ProcessedIndustry[] {
  if (!data?.industries?.length) return []

  return data.industries
    .filter(ind => ind.stocks?.length > 0)
    .map(ind => {
      const stocks = ind.stocks.sort((a, b) => (b.price ?? 0) - (a.price ?? 0))
      const weight = stocks.reduce((sum, s) => sum + (s.price ?? 1), 0)
      const avgChange = stocks.reduce((sum, s) => sum + s.change_pct, 0) / stocks.length
      const upCount = stocks.filter(s => s.change_pct > 0).length
      const downCount = stocks.filter(s => s.change_pct < 0).length
      return { industry: ind.industry, weight, avgChange, stockCount: stocks.length, upCount, downCount, stocks }
    })
    .sort((a, b) => b.weight - a.weight)
}

/* ------------------------------------------------------------------ */
/*  Legend                                                              */
/* ------------------------------------------------------------------ */

const LEGEND = [
  { label: '漲 7%+', color: '#7f1d1d' },
  { label: '漲 3-5%', color: '#b91c1c' },
  { label: '漲 0-3%', color: '#ef4444' },
  { label: '平盤', color: '#374151' },
  { label: '跌 0-3%', color: '#22c55e' },
  { label: '跌 3-5%', color: '#15803d' },
  { label: '跌 5%+', color: '#14532d' },
]

/* ------------------------------------------------------------------ */
/*  Level 1: Industry Grid (像目錄)                                    */
/* ------------------------------------------------------------------ */

function IndustryGrid({
  industries,
  onSelect,
}: {
  industries: ProcessedIndustry[]
  onSelect: (industry: ProcessedIndustry) => void
}) {
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
      gap: 8,
      height: 'calc(100vh - 160px)',
      overflowY: 'auto',
      alignContent: 'start',
    }}>
      {industries.map((ind, i) => (
        <button
          key={ind.industry}
          onClick={() => onSelect(ind)}
          style={{
            background: getHeatColor(ind.avgChange),
            border: '1px solid rgba(255,255,255,0.1)',
            borderRadius: 8,
            padding: '16px 14px',
            cursor: 'pointer',
            textAlign: 'left',
            transition: 'transform 0.15s ease, box-shadow 0.15s ease, opacity 0.3s ease',
            opacity: 0,
            animation: `fadeIn 0.3s ease ${i * 20}ms forwards`,
            position: 'relative',
            overflow: 'hidden',
            minHeight: 100,
          }}
          className="industry-card"
        >
          {/* 產業名稱 */}
          <div style={{ color: '#fff', fontWeight: 700, fontSize: 14, marginBottom: 8, textShadow: '0 1px 3px rgba(0,0,0,0.5)' }}>
            {ind.industry}
          </div>

          {/* 平均漲跌幅 */}
          <div style={{ color: 'rgba(255,255,255,0.95)', fontSize: 22, fontWeight: 800, fontVariantNumeric: 'tabular-nums', marginBottom: 8, textShadow: '0 1px 4px rgba(0,0,0,0.5)' }}>
            {ind.avgChange >= 0 ? '+' : ''}{ind.avgChange.toFixed(2)}%
          </div>

          {/* 股數 & 漲跌比 */}
          <div style={{ display: 'flex', gap: 12, fontSize: 11, color: 'rgba(255,255,255,0.75)' }}>
            <span>{ind.stockCount} 檔</span>
            <span style={{ color: '#fca5a5' }}>▲{ind.upCount}</span>
            <span style={{ color: '#86efac' }}>▼{ind.downCount}</span>
          </div>

          {/* 右下角箭頭 */}
          <div style={{ position: 'absolute', right: 10, bottom: 10, color: 'rgba(255,255,255,0.3)', fontSize: 18 }}>
            →
          </div>
        </button>
      ))}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Level 2: Stock Grid (產業內的個股)                                  */
/* ------------------------------------------------------------------ */

function StockGrid({
  industry,
  onBack,
}: {
  industry: ProcessedIndustry
  onBack: () => void
}) {
  const [tooltip, setTooltip] = useState<{ stock: HeatmapStock; x: number; y: number } | null>(null)

  return (
    <div>
      {/* 返回列 */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        marginBottom: 12,
        padding: '8px 0',
      }}>
        <button
          onClick={onBack}
          style={{
            background: 'var(--secondary)',
            border: '1px solid var(--border)',
            borderRadius: 6,
            padding: '6px 14px',
            cursor: 'pointer',
            color: 'var(--foreground)',
            fontSize: 13,
            fontWeight: 600,
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            transition: 'background 0.15s',
          }}
          className="back-btn"
        >
          ← 返回產業總覽
        </button>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
          <span style={{ color: 'var(--foreground)', fontSize: 18, fontWeight: 700 }}>
            {industry.industry}
          </span>
          <span style={{
            color: getTextColor(industry.avgChange),
            fontSize: 16,
            fontWeight: 700,
            fontVariantNumeric: 'tabular-nums',
          }}>
            {industry.avgChange >= 0 ? '+' : ''}{industry.avgChange.toFixed(2)}%
          </span>
          <span style={{ color: 'var(--muted-foreground)', fontSize: 12 }}>
            {industry.stockCount} 檔
          </span>
        </div>
      </div>

      {/* 個股方塊 */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(110px, 1fr))',
        gap: 4,
        height: 'calc(100vh - 220px)',
        overflowY: 'auto',
        alignContent: 'start',
      }}>
        {industry.stocks.map((stock, i) => (
          <div
            key={stock.stock_id}
            onMouseMove={(e) => setTooltip({ stock, x: e.clientX, y: e.clientY })}
            onMouseLeave={() => setTooltip(null)}
            style={{
              background: getHeatColor(stock.change_pct),
              border: '1px solid rgba(255,255,255,0.08)',
              borderRadius: 4,
              padding: '10px 8px',
              cursor: 'pointer',
              textAlign: 'center',
              transition: 'transform 0.12s ease, box-shadow 0.12s ease, opacity 0.25s ease',
              opacity: 0,
              animation: `fadeIn 0.25s ease ${i * 8}ms forwards`,
              minHeight: 70,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 2,
            }}
            className="stock-cell"
          >
            <span style={{ color: '#fff', fontWeight: 700, fontSize: 13, textShadow: '0 1px 2px rgba(0,0,0,0.5)' }}>
              {stock.stock_id}
            </span>
            <span style={{ color: 'rgba(255,255,255,0.8)', fontSize: 10, lineHeight: 1.2, maxWidth: '100%', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {stock.name}
            </span>
            <span style={{ color: 'rgba(255,255,255,0.9)', fontSize: 12, fontWeight: 600, fontVariantNumeric: 'tabular-nums', textShadow: '0 1px 2px rgba(0,0,0,0.4)' }}>
              {formatPercent(stock.change_pct)}
            </span>
            <span style={{ color: 'rgba(255,255,255,0.6)', fontSize: 10, fontVariantNumeric: 'tabular-nums' }}>
              ${stock.price?.toFixed(0)}
            </span>
          </div>
        ))}
      </div>

      {/* Tooltip */}
      {tooltip && (
        <div style={{
          position: 'fixed',
          left: tooltip.x + 14,
          top: tooltip.y + 14,
          zIndex: 9999,
          pointerEvents: 'none',
          background: '#1e1e2e',
          border: '1px solid #444',
          borderRadius: 8,
          padding: '10px 14px',
          minWidth: 180,
          boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
        }}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, marginBottom: 4 }}>
            <span style={{ color: '#fff', fontWeight: 700, fontSize: 14 }}>{tooltip.stock.stock_id}</span>
            <span style={{ color: '#aaa', fontSize: 12 }}>{tooltip.stock.name}</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ color: '#fff', fontSize: 14, fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>
              ${tooltip.stock.price?.toFixed(2)}
            </span>
            <span style={{
              color: getHeatColor(tooltip.stock.change_pct),
              fontSize: 14,
              fontWeight: 700,
              fontVariantNumeric: 'tabular-nums',
              filter: 'brightness(1.5)',
            }}>
              {formatPercent(tooltip.stock.change_pct)}
            </span>
          </div>
        </div>
      )}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Loading skeleton                                                   */
/* ------------------------------------------------------------------ */

function HeatmapSkeleton() {
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
      gap: 8,
      height: 'calc(100vh - 160px)',
    }}>
      {Array.from({ length: 20 }).map((_, i) => (
        <Skeleton
          key={i}
          style={{ background: 'var(--secondary)', borderRadius: 8, minHeight: 100 }}
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
  const [selectedIndustry, setSelectedIndustry] = useState<ProcessedIndustry | null>(null)

  const industries = useMemo(() => processIndustries(data), [data])

  const handleSelect = useCallback((ind: ProcessedIndustry) => {
    setSelectedIndustry(ind)
  }, [])

  const handleBack = useCallback(() => {
    setSelectedIndustry(null)
  }, [])

  return (
    <div>
      {/* Header */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: 10,
        flexWrap: 'wrap',
        gap: 8,
      }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 12 }}>
          <h1 style={{ color: 'var(--foreground)', fontSize: 20, fontWeight: 700, margin: 0 }}>
            市場熱力圖
          </h1>
          {data?.date && (
            <span style={{ color: 'var(--muted-foreground)', fontSize: 12 }}>{data.date}</span>
          )}
          {!isLoading && !selectedIndustry && (
            <span style={{ color: 'var(--muted-foreground)', fontSize: 12 }}>
              {industries.length} 個產業 · 點擊進入查看個股
            </span>
          )}
        </div>

        {/* Legend */}
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
          {LEGEND.map((item) => (
            <div key={item.label} style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
              <span style={{ width: 12, height: 12, borderRadius: 2, background: item.color, display: 'inline-block' }} />
              <span style={{ color: 'var(--muted-foreground)', fontSize: 10 }}>{item.label}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Content */}
      {isLoading ? (
        <HeatmapSkeleton />
      ) : isError ? (
        <EmptyState title="無法載入熱力圖" description="請確認後端服務是否正常運行" icon="!" />
      ) : selectedIndustry ? (
        <StockGrid industry={selectedIndustry} onBack={handleBack} />
      ) : (
        <IndustryGrid industries={industries} onSelect={handleSelect} />
      )}

      {/* Animations */}
      <style>{`
        @keyframes fadeIn {
          from { opacity: 0; transform: scale(0.92); }
          to { opacity: 1; transform: scale(1); }
        }
        .industry-card:hover {
          transform: scale(1.03) !important;
          box-shadow: 0 4px 20px rgba(255,255,255,0.15) !important;
          border-color: rgba(255,255,255,0.3) !important;
          z-index: 5;
        }
        .stock-cell:hover {
          transform: scale(1.06) !important;
          box-shadow: 0 0 12px rgba(255,255,255,0.25) !important;
          border-color: rgba(255,255,255,0.5) !important;
          z-index: 10;
        }
        .back-btn:hover {
          background: var(--border) !important;
        }
      `}</style>
    </div>
  )
}
