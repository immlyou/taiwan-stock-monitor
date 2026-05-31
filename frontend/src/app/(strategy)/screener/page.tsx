'use client'

import { useMemo, useState } from 'react'
import useSWR from 'swr'
import { fetchAPI } from '@/lib/api/client'
import { useRouter } from 'next/navigation'
import { formatPrice } from '@/lib/utils/format'
import { ratingColor } from '@/lib/constants/chartColors'
import { DataTable } from '@/components/shared/DataTable'
import type { ColumnDef } from '@tanstack/react-table'

interface ValueStock {
  stock_id: string
  price: number
  pe_ratio: number
  pb_ratio: number
  dividend_yield: number
  name?: string
}

interface ValueResponse {
  strategy: string
  preset: string
  date: string
  total_matches: number
  stocks: ValueStock[]
}

type ScoreComponentKey = 'value' | 'growth' | 'momentum' | 'chip' | 'quality' | 'risk'

interface QuantScoreStock {
  stock_id: string
  total_score: number | null
  rating: string
  component_scores: Record<ScoreComponentKey, number | null>
  key_metrics: {
    latest_price?: number | null
    pe_ratio?: number | null
    pb_ratio?: number | null
    dividend_yield?: number | null
    revenue_yoy?: number | null
  }
}

interface QuantScoreResponse {
  date: string
  total: number
  stocks: QuantScoreStock[]
}

type PresetType = 'standard' | 'aggressive' | 'conservative'
type ModeType = 'value' | 'quant'

const PRESETS: { key: PresetType; label: string; desc: string }[] = [
  { key: 'standard', label: '標準', desc: 'PE < 15, PB < 1.5, 殖利率 > 5%' },
  { key: 'aggressive', label: '積極', desc: '寬鬆條件，更多候選股' },
  { key: 'conservative', label: '保守', desc: '嚴格條件，高殖利率優先' },
]

const formatOptional = (value: number | null | undefined, digits = 1) =>
  value == null ? '—' : value.toFixed(digits)

// Quant ranking rows carry their 1-based rank so it survives sorting/paging.
type QuantRow = QuantScoreStock & { rank: number }

const QUANT_COMPONENT_KEYS: { key: ScoreComponentKey; header: string }[] = [
  { key: 'value', header: '價值' },
  { key: 'growth', header: '成長' },
  { key: 'momentum', header: '動能' },
  { key: 'chip', header: '籌碼' },
  { key: 'quality', header: '品質' },
  { key: 'risk', header: '風險' },
]

export default function ScreenerPage() {
  const router = useRouter()
  const [mode, setMode] = useState<ModeType>('value')
  const [preset, setPreset] = useState<PresetType>('standard')
  const [topN, setTopN] = useState(20)
  const [submitted, setSubmitted] = useState(false)
  const [queryKey, setQueryKey] = useState<[ModeType, PresetType, number] | null>(null)

  const { data, isLoading, error } = useSWR<ValueResponse | QuantScoreResponse>(
    queryKey,
    ([m, p, n]) =>
      m === 'quant'
        ? fetchAPI<QuantScoreResponse>(`/screener/scores?top_n=${n}`)
        : fetchAPI<ValueResponse>(`/strategy/value?preset=${p}&top_n=${n}`)
  )

  const handleScreen = () => {
    setSubmitted(true)
    setQueryKey([mode, preset, topN])
  }

  const isQuantResponse = (value: ValueResponse | QuantScoreResponse | undefined): value is QuantScoreResponse =>
    !!value && 'total' in value && 'stocks' in value && !('total_matches' in value)

  const isValueResponse = (value: ValueResponse | QuantScoreResponse | undefined): value is ValueResponse =>
    !!value && 'total_matches' in value

  const quantRows = useMemo<QuantRow[]>(
    () =>
      data && isQuantResponse(data)
        ? data.stocks.map((row, i) => ({ ...row, rank: i + 1 }))
        : [],
    [data]
  )

  const valueRows = useMemo<ValueStock[]>(
    () => (data && isValueResponse(data) ? data.stocks : []),
    [data]
  )

  // 量化排行欄位：排名、代號、總分、評級、價值、成長、動能、籌碼、品質、風險、PE、營收YoY
  const quantColumns = useMemo<ColumnDef<QuantRow, unknown>[]>(
    () => [
      {
        id: '排名',
        accessorKey: 'rank',
        header: '排名',
        cell: ({ row }) => (
          <span className="tabular-nums" style={{ color: 'var(--muted-foreground)' }}>
            {row.original.rank}
          </span>
        ),
      },
      {
        id: '代號',
        accessorKey: 'stock_id',
        header: '代號',
        cell: ({ row }) => (
          <button
            type="button"
            onClick={() => router.push(`/stock/${row.original.stock_id}`)}
            className="font-medium hover:underline"
            style={{ color: 'var(--primary)' }}
          >
            {row.original.stock_id}
          </button>
        ),
      },
      {
        id: '總分',
        accessorFn: (r) => r.total_score ?? -Infinity,
        header: '總分',
        cell: ({ row }) => (
          <span className="tabular-nums font-semibold" style={{ color: 'var(--foreground)' }}>
            {formatOptional(row.original.total_score, 1)}
          </span>
        ),
      },
      {
        id: '評級',
        accessorKey: 'rating',
        header: '評級',
        cell: ({ row }) => (
          <span
            className="inline-flex min-w-7 justify-center rounded px-1.5 py-0.5 text-xs font-bold"
            style={{ background: 'var(--secondary)', color: ratingColor(row.original.rating), border: '1px solid var(--border)' }}
          >
            {row.original.rating}
          </span>
        ),
      },
      ...QUANT_COMPONENT_KEYS.map(
        ({ key, header }): ColumnDef<QuantRow, unknown> => ({
          id: header,
          accessorFn: (r) => r.component_scores[key] ?? -Infinity,
          header,
          cell: ({ row }) => (
            <span className="tabular-nums" style={{ color: 'var(--foreground)' }}>
              {formatOptional(row.original.component_scores[key], 0)}
            </span>
          ),
        })
      ),
      {
        id: 'PE',
        accessorFn: (r) => r.key_metrics.pe_ratio ?? -Infinity,
        header: 'PE',
        cell: ({ row }) => (
          <span className="tabular-nums" style={{ color: 'var(--foreground)' }}>
            {formatOptional(row.original.key_metrics.pe_ratio, 1)}
          </span>
        ),
      },
      {
        id: '營收YoY',
        accessorFn: (r) => r.key_metrics.revenue_yoy ?? -Infinity,
        header: '營收YoY',
        cell: ({ row }) => (
          <span className="tabular-nums" style={{ color: 'var(--foreground)' }}>
            {formatOptional(row.original.key_metrics.revenue_yoy, 1)}%
          </span>
        ),
      },
    ],
    [router]
  )

  // 價值篩選欄位：排名、代號、名稱、現價、PE、PB、殖利率%
  const valueColumns = useMemo<ColumnDef<ValueStock, unknown>[]>(
    () => [
      {
        id: '排名',
        header: '排名',
        enableSorting: false,
        cell: ({ row }) => (
          <span className="tabular-nums" style={{ color: 'var(--muted-foreground)' }}>
            {row.index + 1}
          </span>
        ),
      },
      {
        id: '代號',
        accessorKey: 'stock_id',
        header: '代號',
        cell: ({ row }) => (
          <span className="font-medium" style={{ color: 'var(--primary)' }}>
            {row.original.stock_id}
          </span>
        ),
      },
      {
        id: '名稱',
        accessorFn: (r) => r.name ?? '—',
        header: '名稱',
        cell: ({ row }) => (
          <span style={{ color: 'var(--foreground)' }}>{row.original.name ?? '—'}</span>
        ),
      },
      {
        id: '現價',
        accessorKey: 'price',
        header: '現價',
        cell: ({ row }) => (
          <span className="tabular-nums" style={{ color: 'var(--foreground)' }}>
            {formatPrice(row.original.price)}
          </span>
        ),
      },
      {
        id: 'PE',
        accessorFn: (r) => r.pe_ratio ?? -Infinity,
        header: 'PE',
        cell: ({ row }) => (
          <span className="tabular-nums" style={{ color: 'var(--foreground)' }}>
            {formatOptional(row.original.pe_ratio, 1)}
          </span>
        ),
      },
      {
        id: 'PB',
        accessorKey: 'pb_ratio',
        header: 'PB',
        cell: ({ row }) => (
          <span className="tabular-nums" style={{ color: 'var(--foreground)' }}>
            {formatPrice(row.original.pb_ratio)}
          </span>
        ),
      },
      {
        id: '殖利率%',
        accessorFn: (r) => r.dividend_yield ?? -Infinity,
        header: '殖利率%',
        cell: ({ row }) => (
          <span className="tabular-nums font-semibold" style={{ color: 'var(--primary)' }}>
            {formatOptional(row.original.dividend_yield, 2)}%
          </span>
        ),
      },
    ],
    []
  )

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold" style={{ color: 'var(--foreground)' }}>選股篩選</h1>
        <p className="text-sm mt-1" style={{ color: 'var(--muted-foreground)' }}>價值策略與量化評分排行</p>
      </div>

      {/* 模式選擇 */}
      <div
        className="rounded-lg p-4 mb-4"
        style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
      >
        <p className="text-xs mb-3 font-medium" style={{ color: 'var(--muted-foreground)' }}>篩選模式</p>
        <div className="flex gap-2">
          {[
            { key: 'value' as const, label: '價值策略', desc: '依 PE、PB、殖利率篩選' },
            { key: 'quant' as const, label: '量化評分', desc: '依六構面總分排序' },
          ].map((item) => (
            <button
              key={item.key}
              onClick={() => setMode(item.key)}
              className="flex-1 p-3 rounded-lg text-left transition-colors"
              style={{
                background: mode === item.key ? 'var(--primary)' : 'var(--secondary)',
                color: mode === item.key ? 'var(--primary-foreground)' : 'var(--foreground)',
                border: mode === item.key ? '2px solid var(--primary)' : '2px solid transparent',
              }}
            >
              <p className="text-sm font-semibold">{item.label}</p>
              <p
                className="text-xs mt-0.5"
                style={{ color: mode === item.key ? 'rgba(255,255,255,0.8)' : 'var(--muted-foreground)' }}
              >
                {item.desc}
              </p>
            </button>
          ))}
        </div>
      </div>

      {/* 策略選擇 */}
      {mode === 'value' && (
        <div
          className="rounded-lg p-4 mb-4"
          style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
        >
          <p className="text-xs mb-3 font-medium" style={{ color: 'var(--muted-foreground)' }}>篩選條件預設</p>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
            {PRESETS.map((s) => (
              <button
                key={s.key}
                onClick={() => setPreset(s.key)}
                className="p-3 rounded-lg text-left transition-colors"
                style={{
                  background: preset === s.key ? 'var(--primary)' : 'var(--secondary)',
                  color: preset === s.key ? 'var(--primary-foreground)' : 'var(--foreground)',
                  border: preset === s.key ? '2px solid var(--primary)' : '2px solid transparent',
                }}
              >
                <p className="text-sm font-semibold">{s.label}</p>
                <p
                  className="text-xs mt-0.5"
                  style={{ color: preset === s.key ? 'rgba(255,255,255,0.8)' : 'var(--muted-foreground)' }}
                >
                  {s.desc}
                </p>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* 參數設定 */}
      <div
        className="rounded-lg p-4 mb-4"
        style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
      >
        <p className="text-xs mb-3 font-medium" style={{ color: 'var(--muted-foreground)' }}>篩選參數</p>
        <div className="flex items-end gap-4">
          <div>
            <label className="block text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>結果數量</label>
            <select
              value={topN}
              onChange={(e) => setTopN(Number(e.target.value))}
              className="h-9 w-32 rounded-md border px-3 text-sm"
              style={{ background: 'var(--background)', border: '1px solid var(--border)', color: 'var(--foreground)' }}
            >
              {[10, 20, 30, 50].map(n => (
                <option key={n} value={n}>{n} 支</option>
              ))}
            </select>
          </div>
          <button
            onClick={handleScreen}
            className="h-9 px-6 rounded-md text-sm font-medium"
            style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}
          >
            {mode === 'quant' ? '取得排行' : '開始篩選'}
          </button>
        </div>
      </div>

      {/* 結果 */}
      {!submitted ? null : error ? (
        <div
          className="rounded-lg p-6 text-center"
          style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
        >
          <p style={{ color: 'var(--destructive)' }}>篩選失敗，請稍後再試</p>
        </div>
      ) : isLoading ? (
        <div
          className="rounded-lg p-8 text-center"
          style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
        >
          <p style={{ color: 'var(--muted-foreground)' }}>篩選中...</p>
        </div>
      ) : data && data.stocks.length > 0 && isQuantResponse(data) ? (
        <div
          className="rounded-lg overflow-hidden"
          style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
        >
          <div className="px-4 py-3 flex justify-between items-center border-b" style={{ borderColor: 'var(--border)' }}>
            <h3 className="text-sm font-medium" style={{ color: 'var(--foreground)' }}>
              量化排行 — 全市場 {data.total} 支（顯示 {data.stocks.length} 支）
            </h3>
            <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>{data.date}</span>
          </div>
          <div className="p-4">
            <DataTable
              columns={quantColumns}
              data={quantRows}
              searchable
              searchPlaceholder="搜尋代號 / 評級..."
              exportable
              exportFilename="量化排行"
              pageSize={20}
              emptyMessage="無符合條件的股票"
            />
          </div>
        </div>
      ) : data && data.stocks.length > 0 && isValueResponse(data) ? (
        <div
          className="rounded-lg overflow-hidden"
          style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
        >
          <div className="px-4 py-3 flex justify-between items-center border-b" style={{ borderColor: 'var(--border)' }}>
            <h3 className="text-sm font-medium" style={{ color: 'var(--foreground)' }}>
              篩選結果 — 共 {data.total_matches} 支（顯示 {data.stocks.length} 支）
            </h3>
            <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>{data.date}</span>
          </div>
          <div className="p-4">
            <DataTable
              columns={valueColumns}
              data={valueRows}
              searchable
              searchPlaceholder="搜尋代號 / 名稱..."
              exportable
              exportFilename="選股篩選結果"
              pageSize={20}
              emptyMessage="無符合條件的股票"
            />
          </div>
        </div>
      ) : data ? (
        <div
          className="rounded-lg p-6 text-center"
          style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
        >
          <p style={{ color: 'var(--muted-foreground)' }}>無符合條件的股票</p>
        </div>
      ) : null}
    </div>
  )
}
