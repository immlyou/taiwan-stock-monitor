'use client'

import { useState } from 'react'
import useSWR from 'swr'
import { fetchAPI } from '@/lib/api/client'
import { getChangeColorVar } from '@/lib/utils/format'
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

export default function ChipPage() {
  const [inputCode, setInputCode] = useState('')
  const [stockCode, setStockCode] = useState('')

  const { data, isLoading, error } = useSWR<ChipData>(
    stockCode ? `/stock/${stockCode}/chip` : null,
    fetchAPI
  )

  const handleSearch = () => {
    const code = inputCode.trim()
    if (code) setStockCode(code)
  }

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

  const kpiItems = data ? [
    { label: '外資買賣超', value: data['外資']?.total_shares ?? 0, color: '#3b82f6' },
    { label: '投信買賣超', value: data['投信']?.total_shares ?? 0, color: '#8b5cf6' },
    { label: '自營商買賣超', value: data['自營商']?.total_shares ?? 0, color: '#f59e0b' },
  ] : []

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold" style={{ color: 'var(--foreground)' }}>籌碼分析</h1>
        <p className="text-sm mt-1" style={{ color: 'var(--muted-foreground)' }}>三大法人買賣超、外資持股、融資融券</p>
      </div>

      {/* 股票代號輸入 */}
      <div
        className="rounded-lg p-4 mb-6 flex flex-wrap gap-3 items-end"
        style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
      >
        <div>
          <label className="block text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>股票代號</label>
          <div className="flex gap-2">
            <input
              type="text"
              value={inputCode}
              onChange={(e) => setInputCode(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              placeholder="例：2330"
              className="h-9 w-36 rounded-md border px-3 text-sm"
              style={{ background: 'var(--background)', border: '1px solid var(--border)', color: 'var(--foreground)' }}
            />
            <button
              onClick={handleSearch}
              className="h-9 px-4 rounded-md text-sm font-medium"
              style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}
            >
              查詢
            </button>
          </div>
        </div>
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
                {data.foreign_holding_pct?.toFixed(2) ?? '—'} %
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
                  <Bar dataKey="外資" fill="#3b82f6" radius={[2, 2, 0, 0]} />
                  <Bar dataKey="投信" fill="#8b5cf6" radius={[2, 2, 0, 0]} />
                  <Bar dataKey="自營商" fill="#f59e0b" radius={[2, 2, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* 每日明細表格 */}
          <div className="rounded-lg overflow-hidden" style={{ background: 'var(--card)', border: '1px solid var(--border)' }}>
            <div className="px-4 py-3 border-b" style={{ borderColor: 'var(--border)' }}>
              <h3 className="text-sm font-medium" style={{ color: 'var(--foreground)' }}>每日籌碼明細</h3>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr style={{ background: 'var(--secondary)' }}>
                    {['日期', '外資', '投信', '自營商', '合計'].map(h => (
                      <th key={h} className="text-left py-2 px-4" style={{ color: 'var(--muted-foreground)' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {allDates.map((date) => {
                    const foreign = data['外資']?.daily?.find(d => d.date === date)
                    const trust = data['投信']?.daily?.find(d => d.date === date)
                    const dealer = data['自營商']?.daily?.find(d => d.date === date)
                    const fv = foreign?.shares ?? 0
                    const tv = trust?.shares ?? 0
                    const dv = dealer?.shares ?? 0
                    const total = fv + tv + dv
                    return (
                      <tr key={date} style={{ borderBottom: '1px solid var(--border)' }}>
                        <td className="py-2 px-4" style={{ color: 'var(--foreground)' }}>{date}</td>
                        <td className="py-2 px-4 tabular-nums" style={{ color: getChangeColorVar(fv) }}>
                          {formatShares(fv)}
                        </td>
                        <td className="py-2 px-4 tabular-nums" style={{ color: getChangeColorVar(tv) }}>
                          {formatShares(tv)}
                        </td>
                        <td className="py-2 px-4 tabular-nums" style={{ color: getChangeColorVar(dv) }}>
                          {formatShares(dv)}
                        </td>
                        <td className="py-2 px-4 tabular-nums font-semibold" style={{ color: getChangeColorVar(total) }}>
                          {formatShares(total)}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
