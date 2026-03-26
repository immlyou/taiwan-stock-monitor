'use client'

import { useState } from 'react'
import useSWR from 'swr'
import { fetchAPI } from '@/lib/api/client'
import { getChangeColorVar } from '@/lib/utils/format'

interface ChipRanking {
  code: string
  name: string
  foreignNet: number
  trustNet: number
  dealerNet: number
  totalNet: number
  marginChange: number
  shortChange: number
}

interface ChipData {
  date: string
  foreignTop: ChipRanking[]
  trustTop: ChipRanking[]
  marginTop: ChipRanking[]
}

type ViewType = 'foreign' | 'trust' | 'margin'

const VIEW_LABELS: { key: ViewType; label: string }[] = [
  { key: 'foreign', label: '外資買賣超' },
  { key: 'trust', label: '投信買賣超' },
  { key: 'margin', label: '融資融券' },
]

export default function ChipPage() {
  const [view, setView] = useState<ViewType>('foreign')

  const { data, isLoading, error } = useSWR<ChipData>(
    '/chip/ranking',
    fetchAPI
  )

  const getRows = () => {
    if (!data) return []
    if (view === 'foreign') return data.foreignTop ?? []
    if (view === 'trust') return data.trustTop ?? []
    return data.marginTop ?? []
  }

  const rows = getRows()

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold" style={{ color: 'var(--foreground)' }}>籌碼分析</h1>
        <p className="text-sm mt-1" style={{ color: 'var(--muted-foreground)' }}>
          法人買賣超排行 {data?.date ? `— ${data.date}` : ''}
        </p>
      </div>

      {/* Tab 選擇 */}
      <div
        className="rounded-lg p-4 mb-6"
        style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
      >
        <div className="flex gap-2">
          {VIEW_LABELS.map((v) => (
            <button
              key={v.key}
              onClick={() => setView(v.key)}
              className="px-4 py-2 rounded-md text-sm font-medium transition-colors"
              style={{
                background: view === v.key ? 'var(--primary)' : 'var(--secondary)',
                color: view === v.key ? 'var(--primary-foreground)' : 'var(--foreground)',
              }}
            >
              {v.label}
            </button>
          ))}
        </div>
      </div>

      {error ? (
        <div
          className="rounded-lg p-6 text-center"
          style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
        >
          <p style={{ color: 'var(--destructive)' }}>資料載入失敗</p>
        </div>
      ) : isLoading ? (
        <div className="space-y-2">
          {[...Array(10)].map((_, i) => (
            <div key={i} className="h-10 rounded-md animate-pulse" style={{ background: 'var(--card)' }} />
          ))}
        </div>
      ) : (
        <div
          className="rounded-lg overflow-hidden"
          style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
        >
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ background: 'var(--secondary)' }}>
                  {view === 'margin' ? (
                    ['排名', '代號', '名稱', '融資變化（張）', '融券變化（張）'].map(h => (
                      <th key={h} className="text-left py-3 px-4" style={{ color: 'var(--muted-foreground)' }}>{h}</th>
                    ))
                  ) : (
                    ['排名', '代號', '名稱', '外資買賣超', '投信買賣超', '自營商', '合計'].map(h => (
                      <th key={h} className="text-left py-3 px-4" style={{ color: 'var(--muted-foreground)' }}>{h}</th>
                    ))
                  )}
                </tr>
              </thead>
              <tbody>
                {rows.length > 0 ? rows.map((row, i) => (
                  <tr
                    key={row.code}
                    style={{ borderBottom: '1px solid var(--border)' }}
                    className="hover:opacity-80"
                  >
                    <td className="py-2 px-4 tabular-nums" style={{ color: 'var(--muted-foreground)' }}>{i + 1}</td>
                    <td className="py-2 px-4 font-medium" style={{ color: 'var(--primary)' }}>{row.code}</td>
                    <td className="py-2 px-4" style={{ color: 'var(--foreground)' }}>{row.name}</td>
                    {view === 'margin' ? (
                      <>
                        <td
                          className="py-2 px-4 tabular-nums font-medium"
                          style={{ color: getChangeColorVar(row.marginChange) }}
                        >
                          {row.marginChange > 0 ? '+' : ''}{row.marginChange?.toLocaleString() ?? '—'}
                        </td>
                        <td
                          className="py-2 px-4 tabular-nums font-medium"
                          style={{ color: getChangeColorVar(-row.shortChange) }}
                        >
                          {row.shortChange > 0 ? '+' : ''}{row.shortChange?.toLocaleString() ?? '—'}
                        </td>
                      </>
                    ) : (
                      <>
                        <td className="py-2 px-4 tabular-nums" style={{ color: getChangeColorVar(row.foreignNet) }}>
                          {row.foreignNet > 0 ? '+' : ''}{row.foreignNet?.toLocaleString() ?? '—'}
                        </td>
                        <td className="py-2 px-4 tabular-nums" style={{ color: getChangeColorVar(row.trustNet) }}>
                          {row.trustNet > 0 ? '+' : ''}{row.trustNet?.toLocaleString() ?? '—'}
                        </td>
                        <td className="py-2 px-4 tabular-nums" style={{ color: getChangeColorVar(row.dealerNet) }}>
                          {row.dealerNet > 0 ? '+' : ''}{row.dealerNet?.toLocaleString() ?? '—'}
                        </td>
                        <td
                          className="py-2 px-4 tabular-nums font-semibold"
                          style={{ color: getChangeColorVar(row.totalNet) }}
                        >
                          {row.totalNet > 0 ? '+' : ''}{row.totalNet?.toLocaleString() ?? '—'}
                        </td>
                      </>
                    )}
                  </tr>
                )) : (
                  <tr>
                    <td colSpan={7} className="py-8 text-center" style={{ color: 'var(--muted-foreground)' }}>
                      暫無資料
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
