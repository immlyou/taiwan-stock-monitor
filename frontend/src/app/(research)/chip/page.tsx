'use client'

import { useState } from 'react'
import useSWR from 'swr'
import type { ColumnDef } from '@tanstack/react-table'
import { fetchAPI } from '@/lib/api/client'
import { getChangeColorVar, formatPrice } from '@/lib/utils/format'
import { FLOW } from '@/lib/constants/chartColors'
import { StockInput } from '@/components/shared/StockInput'
import { DataTable } from '@/components/shared/DataTable'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, ReferenceLine
} from 'recharts'

interface DailyChip {
  date: string
  shares: number
}

interface InstitutionChip {
  total_shares: number
  daily: DailyChip[]
}

interface ChipData {
  stock_id: string
  外資: InstitutionChip
  投信: InstitutionChip
  自營商: InstitutionChip
  foreign_holding_pct: number
  margin_buy: number
  margin_sell: number
}

function toThousand(shares: number) {
  return Math.round(shares / 1000)
}

function formatShares(shares: number) {
  const v = toThousand(shares)
  return (v >= 0 ? '+' : '') + v.toLocaleString() + ' 張'
}

interface ChipDetailRow {
  date: string
  外資: number
  投信: number
  自營商: number
  合計: number
}

function sharesCell(value: number, opts?: { semibold?: boolean }) {
  return (
    <span
      className={`tabular-nums${opts?.semibold ? ' font-semibold' : ''}`}
      style={{ color: getChangeColorVar(value) }}
    >
      {formatShares(value)}
    </span>
  )
}

const chipColumns: ColumnDef<ChipDetailRow, unknown>[] = [
  {
    accessorKey: 'date',
    header: '日期',
    cell: ({ getValue }) => (
      <span style={{ color: 'var(--foreground)' }}>{getValue() as string}</span>
    ),
  },
  {
    accessorKey: '外資',
    header: '外資',
    cell: ({ getValue }) => sharesCell(getValue() as number),
  },
  {
    accessorKey: '投信',
    header: '投信',
    cell: ({ getValue }) => sharesCell(getValue() as number),
  },
  {
    accessorKey: '自營商',
    header: '自營商',
    cell: ({ getValue }) => sharesCell(getValue() as number),
  },
  {
    accessorKey: '合計',
    header: '合計',
    cell: ({ getValue }) => sharesCell(getValue() as number, { semibold: true }),
  },
]

export default function ChipPage() {
  const [stockCode, setStockCode] = useState('')

  const { data, isLoading, error } = useSWR<ChipData>(
    stockCode ? `/stock/${stockCode}/chip` : null,
    fetchAPI
  )

  // 合併三大法人每日資料到同一時間軸
  const allDates = Array.from(
    new Set([
      ...(data?.['外資']?.daily ?? []).map(d => d.date),
      ...(data?.['投信']?.daily ?? []).map(d => d.date),
      ...(data?.['自營商']?.daily ?? []).map(d => d.date),
    ])
  ).sort()

  const dailyChartData = allDates.map(date => {
    const foreign = data?.['外資']?.daily?.find(d => d.date === date)
    const trust = data?.['投信']?.daily?.find(d => d.date === date)
    const dealer = data?.['自營商']?.daily?.find(d => d.date === date)
    return {
      date: date.slice(5), // "03-20"
      外資: foreign ? toThousand(foreign.shares) : 0,
      投信: trust ? toThousand(trust.shares) : 0,
      自營商: dealer ? toThousand(dealer.shares) : 0,
    }
  })

  const chipDetailRows: ChipDetailRow[] = allDates.map((date) => {
    const foreign = data?.['外資']?.daily?.find(d => d.date === date)
    const trust = data?.['投信']?.daily?.find(d => d.date === date)
    const dealer = data?.['自營商']?.daily?.find(d => d.date === date)
    const fv = foreign?.shares ?? 0
    const tv = trust?.shares ?? 0
    const dv = dealer?.shares ?? 0
    return { date, 外資: fv, 投信: tv, 自營商: dv, 合計: fv + tv + dv }
  })

  const kpiItems = data ? [
    { label: '外資買賣超', value: data['外資']?.total_shares ?? 0, color: FLOW.foreign },
    { label: '投信買賣超', value: data['投信']?.total_shares ?? 0, color: FLOW.trust },
    { label: '自營商買賣超', value: data['自營商']?.total_shares ?? 0, color: FLOW.dealer },
  ] : []

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold" style={{ color: 'var(--foreground)' }}>籌碼分析</h1>
        <p className="text-sm mt-1" style={{ color: 'var(--muted-foreground)' }}>三大法人買賣超、外資持股、融資融券</p>
      </div>

      {/* 股票代號輸入 */}
      <div
        className="rounded-lg p-4 mb-6"
        style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
      >
        <StockInput
          value={stockCode}
          onChange={setStockCode}
          label="股票代號"
          placeholder="例：2330 或 台積電"
          className="max-w-xs"
        />
      </div>

      {!stockCode ? (
        <div
          className="rounded-lg p-12 text-center"
          style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
        >
          <p style={{ color: 'var(--muted-foreground)' }}>請輸入股票代號開始分析</p>
        </div>
      ) : error ? (
        <div
          className="rounded-lg p-6 text-center"
          style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
        >
          <p style={{ color: 'var(--destructive)' }}>資料載入失敗，請確認股票代號是否正確</p>
        </div>
      ) : isLoading ? (
        <div className="space-y-2">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-16 rounded-md animate-pulse" style={{ background: 'var(--card)' }} />
          ))}
        </div>
      ) : data ? (
        <div className="space-y-4">
          {/* 三大法人 KPI */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {kpiItems.map((item) => {
              const lots = toThousand(item.value)
              return (
                <div
                  key={item.label}
                  className="rounded-lg p-4"
                  style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
                >
                  <p className="text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>{item.label}（近期合計）</p>
                  <p
                    className="text-xl font-bold tabular-nums"
                    style={{ color: getChangeColorVar(item.value) }}
                  >
                    {lots >= 0 ? '+' : ''}{lots.toLocaleString()} 張
                  </p>
                </div>
              )
            })}
          </div>

          {/* 外資持股比率 + 融資融券 */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div
              className="rounded-lg p-4"
              style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
            >
              <p className="text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>外資持股比率</p>
              <p className="text-xl font-bold tabular-nums" style={{ color: 'var(--foreground)' }}>
                {data.foreign_holding_pct != null ? `${formatPrice(data.foreign_holding_pct)} %` : '—'}
              </p>
            </div>
            <div
              className="rounded-lg p-4"
              style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
            >
              <p className="text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>融資餘額</p>
              <p className="text-xl font-bold tabular-nums" style={{ color: 'var(--foreground)' }}>
                {data.margin_buy != null ? data.margin_buy.toLocaleString() + ' 張' : '—'}
              </p>
            </div>
            <div
              className="rounded-lg p-4"
              style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
            >
              <p className="text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>融券餘額</p>
              <p className="text-xl font-bold tabular-nums" style={{ color: 'var(--foreground)' }}>
                {data.margin_sell != null ? data.margin_sell.toLocaleString() + ' 張' : '—'}
              </p>
            </div>
          </div>

          {/* 每日買賣超長條圖 */}
          {dailyChartData.length > 0 && (
            <div className="rounded-lg p-4" style={{ background: 'var(--card)', border: '1px solid var(--border)' }}>
              <h3 className="text-sm font-medium mb-3" style={{ color: 'var(--muted-foreground)' }}>三大法人每日買賣超（張）</h3>
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={dailyChartData} barGap={2}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="date" tick={{ fill: 'var(--muted-foreground)', fontSize: 10 }} />
                  <YAxis tick={{ fill: 'var(--muted-foreground)', fontSize: 10 }} />
                  <Tooltip
                    contentStyle={{ background: 'var(--card)', border: '1px solid var(--border)', color: 'var(--foreground)' }}
                    formatter={(v, name) => {
                      const n = Number(v ?? 0)
                      return [`${n >= 0 ? '+' : ''}${n.toLocaleString()} 張`, String(name)]
                    }}
                  />
                  <Legend />
                  <ReferenceLine y={0} stroke="var(--border)" />
                  <Bar dataKey="外資" fill={FLOW.foreign} radius={[2, 2, 0, 0]} />
                  <Bar dataKey="投信" fill={FLOW.trust} radius={[2, 2, 0, 0]} />
                  <Bar dataKey="自營商" fill={FLOW.dealer} radius={[2, 2, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* 每日明細表格 */}
          <div className="rounded-lg overflow-hidden" style={{ background: 'var(--card)', border: '1px solid var(--border)' }}>
            <div className="px-4 py-3 border-b" style={{ borderColor: 'var(--border)' }}>
              <h3 className="text-sm font-medium" style={{ color: 'var(--foreground)' }}>每日籌碼明細</h3>
            </div>
            <div className="p-4">
              <DataTable
                columns={chipColumns}
                data={chipDetailRows}
                searchable
                exportable
                exportFilename={`chip_${data.stock_id}`}
                pageSize={20}
              />
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
