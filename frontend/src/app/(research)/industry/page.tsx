'use client'

import useSWR from 'swr'
import { fetchAPI } from '@/lib/api/client'
import { getChangeColorVar } from '@/lib/utils/format'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell
} from 'recharts'

// 對應 GET /market/industries
interface Industry {
  industry: string
  stock_count: number
  avg_change_pct: number
  up_count: number
  down_count: number
}

interface IndustryResponse {
  date: string
  total_industries: number
  industries: Industry[]
}

export default function IndustryPage() {
  const { data, isLoading, error } = useSWR<IndustryResponse>(
    '/market/industries',
    fetchAPI
  )

  const sorted = data?.industries
    ? [...data.industries].sort((a, b) => b.avg_change_pct - a.avg_change_pct)
    : []

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold" style={{ color: 'var(--foreground)' }}>產業分析</h1>
        <p className="text-sm mt-1" style={{ color: 'var(--muted-foreground)' }}>
          產業強弱排行 {data?.date ? `— ${data.date}` : ''}
          {data?.total_industries ? `（共 ${data.total_industries} 個產業）` : ''}
        </p>
      </div>

      {error ? (
        <div
          className="rounded-lg p-6 text-center"
          style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
        >
          <p style={{ color: 'var(--destructive)' }}>資料載入失敗</p>
        </div>
      ) : isLoading ? (
        <div className="space-y-4">
          {[...Array(3)].map((_, i) => (
            <div
              key={i}
              className="h-20 rounded-lg animate-pulse"
              style={{ background: 'var(--card)' }}
            />
          ))}
        </div>
      ) : (
        <div className="space-y-4">
          {/* 漲跌幅 BarChart */}
          <div
            className="rounded-lg p-4"
            style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
          >
            <h3 className="text-sm font-medium mb-3" style={{ color: 'var(--muted-foreground)' }}>
              產業漲跌幅排行
            </h3>
            <ResponsiveContainer width="100%" height={Math.max(360, sorted.length * 20)}>
              <BarChart data={sorted} layout="vertical" margin={{ left: 100, right: 60 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" horizontal={false} />
                <XAxis
                  type="number"
                  tick={{ fill: 'var(--muted-foreground)', fontSize: 11 }}
                  tickFormatter={(v) => `${v > 0 ? '+' : ''}${v}%`}
                />
                <YAxis
                  type="category"
                  dataKey="industry"
                  tick={{ fill: 'var(--foreground)', fontSize: 10 }}
                  width={100}
                />
                <Tooltip
                  contentStyle={{ background: 'var(--card)', border: '1px solid var(--border)', color: 'var(--foreground)' }}
                  formatter={(value: unknown) => {
                    const v = value as number
                    return [`${v > 0 ? '+' : ''}${v.toFixed(2)}%`, '漲跌幅']
                  }}
                />
                <Bar dataKey="avg_change_pct" name="漲跌幅" radius={[0, 4, 4, 0]}>
                  {sorted.map((entry, i) => (
                    <Cell key={i} fill={entry.avg_change_pct >= 0 ? 'var(--stock-up)' : 'var(--stock-down)'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* 產業列表 */}
          <div
            className="rounded-lg overflow-hidden"
            style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
          >
            <div className="px-4 py-3 border-b" style={{ borderColor: 'var(--border)' }}>
              <h3 className="text-sm font-medium" style={{ color: 'var(--foreground)' }}>產業詳細資料</h3>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr style={{ background: 'var(--secondary)' }}>
                    {['排名', '產業名稱', '漲跌幅', '上漲', '下跌', '持平', '股票數'].map(h => (
                      <th key={h} className="text-left py-2 px-4" style={{ color: 'var(--muted-foreground)' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {sorted.map((ind, i) => {
                    const flat = ind.stock_count - ind.up_count - ind.down_count
                    return (
                      <tr
                        key={ind.industry}
                        style={{ borderBottom: '1px solid var(--border)' }}
                        className="hover:opacity-80 transition-opacity"
                      >
                        <td className="py-2 px-4 tabular-nums" style={{ color: 'var(--muted-foreground)' }}>
                          {i + 1}
                        </td>
                        <td className="py-2 px-4 font-medium" style={{ color: 'var(--foreground)' }}>
                          {ind.industry}
                        </td>
                        <td
                          className="py-2 px-4 font-semibold tabular-nums"
                          style={{ color: getChangeColorVar(ind.avg_change_pct) }}
                        >
                          {ind.avg_change_pct > 0 ? '+' : ''}{ind.avg_change_pct.toFixed(2)}%
                        </td>
                        <td className="py-2 px-4 tabular-nums" style={{ color: 'var(--stock-up)' }}>
                          {ind.up_count}
                        </td>
                        <td className="py-2 px-4 tabular-nums" style={{ color: 'var(--stock-down)' }}>
                          {ind.down_count}
                        </td>
                        <td className="py-2 px-4 tabular-nums" style={{ color: 'var(--muted-foreground)' }}>
                          {flat >= 0 ? flat : 0}
                        </td>
                        <td className="py-2 px-4 tabular-nums" style={{ color: 'var(--foreground)' }}>
                          {ind.stock_count}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
