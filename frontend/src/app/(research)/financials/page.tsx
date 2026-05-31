'use client'

import { useState } from 'react'
import useSWR from 'swr'
import { fetchAPI } from '@/lib/api/client'
import { StockInput } from '@/components/shared/StockInput'
import { CHART_SERIES, UP, DOWN } from '@/lib/constants/chartColors'
import { formatCurrency, formatDate, formatPercent } from '@/lib/utils/format'
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend
} from 'recharts'

interface TimePoint {
  date: string
  value: number
}

interface FinancialData {
  stock_id: string
  months: number
  monthly_revenue: TimePoint[]
  revenue_yoy: TimePoint[]
  revenue_mom: TimePoint[]
  pe_ratio: TimePoint[]
  pb_ratio: TimePoint[]
  dividend_yield: TimePoint[]
}

// "2025-04-10" -> "2025/04"（沿用 format.ts 的 formatDate，取年月）
const toYearMonth = (dateStr: string) => formatDate(dateStr).slice(0, 7)

export default function FinancialsPage() {
  const [stockCode, setStockCode] = useState('')

  const { data, isLoading, error } = useSWR<FinancialData>(
    stockCode ? `/stock/${stockCode}/financials` : null,
    fetchAPI
  )

  const revenueChartData = (data?.monthly_revenue ?? []).map(p => ({
    date: toYearMonth(p.date),
    value: p.value,
  }))

  const yoyChartData = (data?.revenue_yoy ?? []).map(p => ({
    date: toYearMonth(p.date),
    value: p.value,
  }))

  const momChartData = (data?.revenue_mom ?? []).map(p => ({
    date: toYearMonth(p.date),
    value: p.value,
  }))

  // 合併 PE/PB/DY 到同一個日期軸（取交集日期）
  const valChartData = (data?.pe_ratio ?? []).map(p => {
    const pbPoint = data?.pb_ratio?.find(x => x.date === p.date)
    const dyPoint = data?.dividend_yield?.find(x => x.date === p.date)
    return {
      date: toYearMonth(p.date),
      pe: p.value,
      pb: pbPoint?.value ?? null,
      dy: dyPoint?.value ?? null,
    }
  })

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold" style={{ color: 'var(--foreground)' }}>財報分析</h1>
        <p className="text-sm mt-1" style={{ color: 'var(--muted-foreground)' }}>月營收、年增率、本益比、殖利率趨勢</p>
      </div>

      {/* 控制列 */}
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
        <div
          className="rounded-lg p-12 text-center"
          style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
        >
          <p style={{ color: 'var(--muted-foreground)' }}>載入 {stockCode} 財報資料中...</p>
        </div>
      ) : data ? (
        <div className="space-y-4">
          {/* 月營收長條圖 */}
          <div className="rounded-lg p-4" style={{ background: 'var(--card)', border: '1px solid var(--border)' }}>
            <h3 className="text-sm font-medium mb-3" style={{ color: 'var(--muted-foreground)' }}>月營收</h3>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={revenueChartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis dataKey="date" tick={{ fill: 'var(--muted-foreground)', fontSize: 10 }} />
                <YAxis tick={{ fill: 'var(--muted-foreground)', fontSize: 10 }} tickFormatter={(v) => (v / 1e8).toFixed(0) + '億'} />
                <Tooltip
                  contentStyle={{ background: 'var(--card)', border: '1px solid var(--border)', color: 'var(--foreground)' }}
                  formatter={(v) => [formatCurrency(Number(v ?? 0), { compact: true, decimals: 1 }), '月營收']}
                />
                <Bar dataKey="value" fill="var(--primary)" name="月營收" radius={[2, 2, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* 年增率 / 月增率 */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="rounded-lg p-4" style={{ background: 'var(--card)', border: '1px solid var(--border)' }}>
              <h3 className="text-sm font-medium mb-3" style={{ color: 'var(--muted-foreground)' }}>營收年增率 YoY (%)</h3>
              <ResponsiveContainer width="100%" height={180}>
                <LineChart data={yoyChartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="date" tick={{ fill: 'var(--muted-foreground)', fontSize: 10 }} />
                  <YAxis tick={{ fill: 'var(--muted-foreground)', fontSize: 10 }} tickFormatter={(v) => `${v}%`} />
                  <Tooltip
                    contentStyle={{ background: 'var(--card)', border: '1px solid var(--border)', color: 'var(--foreground)' }}
                    formatter={(v) => [`${Number(v ?? 0).toFixed(2)}%`, '年增率']}
                  />
                  <Line type="monotone" dataKey="value" stroke={CHART_SERIES[0]} dot={false} strokeWidth={2} name="YoY%" />
                </LineChart>
              </ResponsiveContainer>
            </div>
            <div className="rounded-lg p-4" style={{ background: 'var(--card)', border: '1px solid var(--border)' }}>
              <h3 className="text-sm font-medium mb-3" style={{ color: 'var(--muted-foreground)' }}>營收月增率 MoM (%)</h3>
              <ResponsiveContainer width="100%" height={180}>
                <LineChart data={momChartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="date" tick={{ fill: 'var(--muted-foreground)', fontSize: 10 }} />
                  <YAxis tick={{ fill: 'var(--muted-foreground)', fontSize: 10 }} tickFormatter={(v) => `${v}%`} />
                  <Tooltip
                    contentStyle={{ background: 'var(--card)', border: '1px solid var(--border)', color: 'var(--foreground)' }}
                    formatter={(v) => [`${Number(v ?? 0).toFixed(2)}%`, '月增率']}
                  />
                  <Line type="monotone" dataKey="value" stroke={CHART_SERIES[1]} dot={false} strokeWidth={2} name="MoM%" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* PE / PB / 殖利率 */}
          {valChartData.length > 0 && (
            <div className="rounded-lg p-4" style={{ background: 'var(--card)', border: '1px solid var(--border)' }}>
              <h3 className="text-sm font-medium mb-3" style={{ color: 'var(--muted-foreground)' }}>PE / PB / 殖利率趨勢</h3>
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={valChartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="date" tick={{ fill: 'var(--muted-foreground)', fontSize: 10 }} />
                  <YAxis tick={{ fill: 'var(--muted-foreground)', fontSize: 10 }} />
                  <Tooltip contentStyle={{ background: 'var(--card)', border: '1px solid var(--border)', color: 'var(--foreground)' }} />
                  <Legend />
                  <Line type="monotone" dataKey="pe" stroke={CHART_SERIES[2]} dot={false} strokeWidth={2} name="本益比 PE" connectNulls />
                  <Line type="monotone" dataKey="pb" stroke={CHART_SERIES[3]} dot={false} strokeWidth={2} name="股價淨值比 PB" connectNulls />
                  <Line type="monotone" dataKey="dy" stroke={CHART_SERIES[0]} dot={false} strokeWidth={2} name="殖利率 DY%" connectNulls />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* 月營收明細表格 */}
          <div className="rounded-lg overflow-hidden" style={{ background: 'var(--card)', border: '1px solid var(--border)' }}>
            <div className="px-4 py-3 border-b" style={{ borderColor: 'var(--border)' }}>
              <h3 className="text-sm font-medium" style={{ color: 'var(--foreground)' }}>月營收明細</h3>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr style={{ background: 'var(--secondary)' }}>
                    {['日期', '月營收', '年增率 YoY', '月增率 MoM'].map(h => (
                      <th key={h} className="text-left py-2 px-4" style={{ color: 'var(--muted-foreground)' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.monthly_revenue.map((r, i) => {
                    const yoy = data.revenue_yoy[i]
                    const mom = data.revenue_mom[i]
                    return (
                      <tr key={r.date} style={{ borderBottom: '1px solid var(--border)' }}>
                        <td className="py-2 px-4" style={{ color: 'var(--foreground)' }}>{r.date.slice(0, 7)}</td>
                        <td className="py-2 px-4 tabular-nums" style={{ color: 'var(--foreground)' }}>{formatCurrency(r.value, { compact: true, decimals: 1 })}</td>
                        <td
                          className="py-2 px-4 tabular-nums"
                          style={{ color: yoy?.value >= 0 ? UP : DOWN }}
                        >
                          {yoy ? formatPercent(yoy.value, 2) : '—'}
                        </td>
                        <td
                          className="py-2 px-4 tabular-nums"
                          style={{ color: mom?.value >= 0 ? UP : DOWN }}
                        >
                          {mom ? formatPercent(mom.value, 2) : '—'}
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
