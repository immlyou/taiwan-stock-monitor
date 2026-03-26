'use client'

import { useState } from 'react'
import useSWR from 'swr'
import { fetchAPI } from '@/lib/api/client'
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend
} from 'recharts'

interface FinancialData {
  quarters: Array<{
    period: string
    revenue: number
    grossProfit: number
    operatingIncome: number
    netIncome: number
    eps: number
    roe: number
    grossMargin: number
    operatingMargin: number
    netMargin: number
  }>
  annual: Array<{
    year: number
    revenue: number
    eps: number
    roe: number
    dividendPerShare: number
  }>
}

export default function FinancialsPage() {
  const [inputCode, setInputCode] = useState('')
  const [stockCode, setStockCode] = useState('')
  const [viewMode, setViewMode] = useState<'quarter' | 'annual'>('quarter')

  const { data, isLoading, error } = useSWR<FinancialData>(
    stockCode ? `/stocks/${stockCode}/financials` : null,
    fetchAPI
  )

  const handleSearch = () => {
    const code = inputCode.trim().toUpperCase()
    if (code) setStockCode(code)
  }

  const chartData = (viewMode === 'quarter' ? (data?.quarters ?? []) : (data?.annual ?? [])) as Record<string, unknown>[]
  const dateKey = viewMode === 'quarter' ? 'period' : 'year'

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold" style={{ color: 'var(--foreground)' }}>財報分析</h1>
        <p className="text-sm mt-1" style={{ color: 'var(--muted-foreground)' }}>EPS、ROE、毛利率、營收趨勢</p>
      </div>

      {/* 控制列 */}
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
        <div>
          <label className="block text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>顯示方式</label>
          <div className="flex gap-1">
            {([{ key: 'quarter', label: '季報' }, { key: 'annual', label: '年報' }] as const).map((v) => (
              <button
                key={v.key}
                onClick={() => setViewMode(v.key)}
                className="h-9 px-4 rounded-md text-sm font-medium"
                style={{
                  background: viewMode === v.key ? 'var(--primary)' : 'var(--secondary)',
                  color: viewMode === v.key ? 'var(--primary-foreground)' : 'var(--foreground)',
                }}
              >
                {v.label}
              </button>
            ))}
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
        <div
          className="rounded-lg p-12 text-center"
          style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
        >
          <p style={{ color: 'var(--muted-foreground)' }}>載入 {stockCode} 財報資料中...</p>
        </div>
      ) : data ? (
        <div className="space-y-4">
          {/* 營收趨勢 */}
          <div className="rounded-lg p-4" style={{ background: 'var(--card)', border: '1px solid var(--border)' }}>
            <h3 className="text-sm font-medium mb-3" style={{ color: 'var(--muted-foreground)' }}>營收趨勢</h3>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis dataKey={dateKey} tick={{ fill: 'var(--muted-foreground)', fontSize: 10 }} />
                <YAxis tick={{ fill: 'var(--muted-foreground)', fontSize: 10 }} />
                <Tooltip contentStyle={{ background: 'var(--card)', border: '1px solid var(--border)', color: 'var(--foreground)' }} />
                <Bar dataKey="revenue" fill="var(--primary)" name="營收" radius={[2, 2, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* EPS & ROE */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="rounded-lg p-4" style={{ background: 'var(--card)', border: '1px solid var(--border)' }}>
              <h3 className="text-sm font-medium mb-3" style={{ color: 'var(--muted-foreground)' }}>每股盈餘 EPS</h3>
              <ResponsiveContainer width="100%" height={180}>
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey={dateKey} tick={{ fill: 'var(--muted-foreground)', fontSize: 10 }} />
                  <YAxis tick={{ fill: 'var(--muted-foreground)', fontSize: 10 }} />
                  <Tooltip contentStyle={{ background: 'var(--card)', border: '1px solid var(--border)', color: 'var(--foreground)' }} />
                  <Line type="monotone" dataKey="eps" stroke="#f59e0b" dot={true} strokeWidth={2} name="EPS" />
                </LineChart>
              </ResponsiveContainer>
            </div>
            <div className="rounded-lg p-4" style={{ background: 'var(--card)', border: '1px solid var(--border)' }}>
              <h3 className="text-sm font-medium mb-3" style={{ color: 'var(--muted-foreground)' }}>股東權益報酬率 ROE</h3>
              <ResponsiveContainer width="100%" height={180}>
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey={dateKey} tick={{ fill: 'var(--muted-foreground)', fontSize: 10 }} />
                  <YAxis tick={{ fill: 'var(--muted-foreground)', fontSize: 10 }} />
                  <Tooltip contentStyle={{ background: 'var(--card)', border: '1px solid var(--border)', color: 'var(--foreground)' }} />
                  <Line type="monotone" dataKey="roe" stroke="#8b5cf6" dot={true} strokeWidth={2} name="ROE %" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* 利潤率 */}
          {viewMode === 'quarter' && (
            <div className="rounded-lg p-4" style={{ background: 'var(--card)', border: '1px solid var(--border)' }}>
              <h3 className="text-sm font-medium mb-3" style={{ color: 'var(--muted-foreground)' }}>利潤率趨勢</h3>
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={data.quarters}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="period" tick={{ fill: 'var(--muted-foreground)', fontSize: 10 }} />
                  <YAxis tick={{ fill: 'var(--muted-foreground)', fontSize: 10 }} tickFormatter={(v) => `${v}%`} />
                  <Tooltip contentStyle={{ background: 'var(--card)', border: '1px solid var(--border)', color: 'var(--foreground)' }} />
                  <Legend />
                  <Line type="monotone" dataKey="grossMargin" stroke="#22c55e" dot={false} strokeWidth={2} name="毛利率" />
                  <Line type="monotone" dataKey="operatingMargin" stroke="#3b82f6" dot={false} strokeWidth={2} name="營業利益率" />
                  <Line type="monotone" dataKey="netMargin" stroke="#f59e0b" dot={false} strokeWidth={2} name="淨利率" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* 明細表格 */}
          <div className="rounded-lg overflow-hidden" style={{ background: 'var(--card)', border: '1px solid var(--border)' }}>
            <div className="px-4 py-3 border-b" style={{ borderColor: 'var(--border)' }}>
              <h3 className="text-sm font-medium" style={{ color: 'var(--foreground)' }}>財報明細</h3>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr style={{ background: 'var(--secondary)' }}>
                    {viewMode === 'quarter'
                      ? ['期間', '營收', '毛利', '營益', '淨利', 'EPS', 'ROE%', '毛利率%'].map(h => (
                          <th key={h} className="text-left py-2 px-4" style={{ color: 'var(--muted-foreground)' }}>{h}</th>
                        ))
                      : ['年度', '營收', 'EPS', 'ROE%', '現金股利'].map(h => (
                          <th key={h} className="text-left py-2 px-4" style={{ color: 'var(--muted-foreground)' }}>{h}</th>
                        ))}
                  </tr>
                </thead>
                <tbody>
                  {viewMode === 'quarter'
                    ? data.quarters.map((q) => (
                        <tr key={q.period} style={{ borderBottom: '1px solid var(--border)' }}>
                          <td className="py-2 px-4" style={{ color: 'var(--foreground)' }}>{q.period}</td>
                          <td className="py-2 px-4 tabular-nums" style={{ color: 'var(--foreground)' }}>{(q.revenue / 1e8).toFixed(1)} 億</td>
                          <td className="py-2 px-4 tabular-nums" style={{ color: 'var(--foreground)' }}>{(q.grossProfit / 1e8).toFixed(1)} 億</td>
                          <td className="py-2 px-4 tabular-nums" style={{ color: 'var(--foreground)' }}>{(q.operatingIncome / 1e8).toFixed(1)} 億</td>
                          <td className="py-2 px-4 tabular-nums" style={{ color: 'var(--foreground)' }}>{(q.netIncome / 1e8).toFixed(1)} 億</td>
                          <td className="py-2 px-4 tabular-nums font-semibold" style={{ color: q.eps >= 0 ? 'var(--stock-up)' : 'var(--stock-down)' }}>{q.eps.toFixed(2)}</td>
                          <td className="py-2 px-4 tabular-nums" style={{ color: 'var(--foreground)' }}>{q.roe.toFixed(2)}%</td>
                          <td className="py-2 px-4 tabular-nums" style={{ color: 'var(--foreground)' }}>{q.grossMargin.toFixed(2)}%</td>
                        </tr>
                      ))
                    : data.annual.map((a) => (
                        <tr key={a.year} style={{ borderBottom: '1px solid var(--border)' }}>
                          <td className="py-2 px-4" style={{ color: 'var(--foreground)' }}>{a.year}</td>
                          <td className="py-2 px-4 tabular-nums" style={{ color: 'var(--foreground)' }}>{(a.revenue / 1e8).toFixed(1)} 億</td>
                          <td className="py-2 px-4 tabular-nums font-semibold" style={{ color: a.eps >= 0 ? 'var(--stock-up)' : 'var(--stock-down)' }}>{a.eps.toFixed(2)}</td>
                          <td className="py-2 px-4 tabular-nums" style={{ color: 'var(--foreground)' }}>{a.roe.toFixed(2)}%</td>
                          <td className="py-2 px-4 tabular-nums" style={{ color: 'var(--foreground)' }}>{a.dividendPerShare.toFixed(2)}</td>
                        </tr>
                      ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
