'use client'

import { useState } from 'react'
import useSWR from 'swr'
import { fetchAPI } from '@/lib/api/client'
import { getChangeColorVar } from '@/lib/utils/format'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend
} from 'recharts'

interface StockDataPoint {
  date: string
  price: number
  normalized: number
}

interface StockCompare {
  stock_id: string
  name: string
  base_price: number
  latest_price: number
  total_return_pct: number
  data: StockDataPoint[]
}

interface CompareResponse {
  days: number
  stocks: StockCompare[]
}

// Transform API response into recharts-friendly format
function buildChartData(stocks: StockCompare[]) {
  if (!stocks.length) return []
  const allDates = stocks[0].data.map(d => d.date)
  return allDates.map((date, i) => {
    const point: Record<string, string | number> = { date }
    stocks.forEach(s => {
      point[s.stock_id] = s.data[i]?.normalized ?? 100
    })
    return point
  })
}

const COLORS = ['#3b82f6', '#ef4444', '#22c55e', '#f59e0b', '#8b5cf6']
const MAX_STOCKS = 5

export default function ComparePage() {
  const [inputCode, setInputCode] = useState('')
  const [selectedCodes, setSelectedCodes] = useState<string[]>([])
  const [submitted, setSubmitted] = useState<string[]>([])

  const { data, isLoading, error } = useSWR<CompareResponse>(
    submitted.length >= 2 ? `/stocks/compare?ids=${submitted.join(',')}&days=60` : null,
    fetchAPI
  )

  const addCode = () => {
    const code = inputCode.trim().toUpperCase()
    if (!code || selectedCodes.includes(code) || selectedCodes.length >= MAX_STOCKS) return
    setSelectedCodes(prev => [...prev, code])
    setInputCode('')
  }

  const removeCode = (code: string) => {
    setSelectedCodes(prev => prev.filter(c => c !== code))
  }

  const handleCompare = () => {
    if (selectedCodes.length >= 2) {
      setSubmitted([...selectedCodes])
    }
  }

  const chartData = data ? buildChartData(data.stocks) : []

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold" style={{ color: 'var(--foreground)' }}>比較分析</h1>
        <p className="text-sm mt-1" style={{ color: 'var(--muted-foreground)' }}>多股績效比較（最多 5 支）</p>
      </div>

      {/* 選股面板 */}
      <div
        className="rounded-lg p-4 mb-6"
        style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
      >
        <div className="flex flex-wrap gap-2 items-end">
          <div className="flex gap-2">
            <input
              type="text"
              value={inputCode}
              onChange={(e) => setInputCode(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && addCode()}
              placeholder="輸入股票代號"
              className="h-9 w-36 rounded-md border px-3 text-sm"
              style={{
                background: 'var(--background)',
                border: '1px solid var(--border)',
                color: 'var(--foreground)',
              }}
            />
            <button
              onClick={addCode}
              disabled={selectedCodes.length >= MAX_STOCKS}
              className="h-9 px-4 rounded-md text-sm font-medium disabled:opacity-50"
              style={{ background: 'var(--secondary)', color: 'var(--foreground)' }}
            >
              新增
            </button>
          </div>

          {/* 已選標籤 */}
          {selectedCodes.map((code, i) => (
            <div
              key={code}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium"
              style={{ background: COLORS[i] + '33', color: COLORS[i], border: `1px solid ${COLORS[i]}55` }}
            >
              {code}
              <button
                onClick={() => removeCode(code)}
                className="ml-1 text-xs opacity-70 hover:opacity-100"
              >
                x
              </button>
            </div>
          ))}

          <button
            onClick={handleCompare}
            disabled={selectedCodes.length < 2}
            className="h-9 px-5 rounded-md text-sm font-medium disabled:opacity-50 ml-auto"
            style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}
          >
            開始比較
          </button>
        </div>
        {selectedCodes.length < 2 && (
          <p className="text-xs mt-2" style={{ color: 'var(--muted-foreground)' }}>
            請至少選擇 2 支股票進行比較
          </p>
        )}
      </div>

      {/* 結果 */}
      {!submitted.length ? null : error ? (
        <div
          className="rounded-lg p-6 text-center"
          style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
        >
          <p style={{ color: 'var(--destructive)' }}>資料載入失敗</p>
        </div>
      ) : isLoading ? (
        <div
          className="rounded-lg p-12 text-center"
          style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
        >
          <p style={{ color: 'var(--muted-foreground)' }}>比較中...</p>
        </div>
      ) : data ? (
        <div className="space-y-4">
          {/* 績效折線圖 */}
          <div
            className="rounded-lg p-4"
            style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
          >
            <h3 className="text-sm font-medium mb-3" style={{ color: 'var(--muted-foreground)' }}>
              相對報酬率走勢（基期=100，近 {data.days} 日）
            </h3>
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis
                  dataKey="date"
                  tick={{ fill: 'var(--muted-foreground)', fontSize: 10 }}
                  tickFormatter={(v: string) => v.slice(5)}
                  interval={Math.floor(chartData.length / 8)}
                />
                <YAxis tick={{ fill: 'var(--muted-foreground)', fontSize: 10 }} />
                <Tooltip
                  contentStyle={{ background: 'var(--card)', border: '1px solid var(--border)', color: 'var(--foreground)' }}
                />
                <Legend />
                {data.stocks.map((s, i) => (
                  <Line
                    key={s.stock_id}
                    type="monotone"
                    dataKey={s.stock_id}
                    stroke={COLORS[i]}
                    dot={false}
                    strokeWidth={2}
                    name={`${s.stock_id} ${s.name}`}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* 指標對比表格 */}
          <div
            className="rounded-lg overflow-hidden"
            style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
          >
            <div className="px-4 py-3 border-b" style={{ borderColor: 'var(--border)' }}>
              <h3 className="text-sm font-medium" style={{ color: 'var(--foreground)' }}>指標對比</h3>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr style={{ background: 'var(--secondary)' }}>
                    {['股票', '基期價', '最新價', '總報酬'].map(h => (
                      <th key={h} className="text-left py-2 px-4" style={{ color: 'var(--muted-foreground)' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.stocks.map((s, i) => (
                    <tr key={s.stock_id} style={{ borderBottom: '1px solid var(--border)' }}>
                      <td className="py-2 px-4 font-medium" style={{ color: COLORS[i] }}>
                        {s.stock_id}
                        <span className="ml-1 text-xs" style={{ color: 'var(--muted-foreground)' }}>{s.name}</span>
                      </td>
                      <td className="py-2 px-4 tabular-nums" style={{ color: 'var(--foreground)' }}>
                        {s.base_price.toFixed(2)}
                      </td>
                      <td className="py-2 px-4 tabular-nums" style={{ color: 'var(--foreground)' }}>
                        {s.latest_price.toFixed(2)}
                      </td>
                      <td className="py-2 px-4 tabular-nums font-semibold" style={{ color: getChangeColorVar(s.total_return_pct) }}>
                        {s.total_return_pct > 0 ? '+' : ''}{s.total_return_pct.toFixed(2)}%
                      </td>
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
