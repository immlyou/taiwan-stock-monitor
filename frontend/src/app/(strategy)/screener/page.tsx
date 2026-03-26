'use client'

import { useState } from 'react'
import useSWR from 'swr'
import { fetchAPI } from '@/lib/api/client'

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

type PresetType = 'standard' | 'aggressive' | 'conservative'

const PRESETS: { key: PresetType; label: string; desc: string }[] = [
  { key: 'standard', label: '標準', desc: 'PE < 15, PB < 1.5, 殖利率 > 5%' },
  { key: 'aggressive', label: '積極', desc: '寬鬆條件，更多候選股' },
  { key: 'conservative', label: '保守', desc: '嚴格條件，高殖利率優先' },
]

export default function ScreenerPage() {
  const [preset, setPreset] = useState<PresetType>('standard')
  const [topN, setTopN] = useState(20)
  const [submitted, setSubmitted] = useState(false)
  const [queryKey, setQueryKey] = useState<[string, PresetType, number] | null>(null)

  const { data, isLoading, error } = useSWR<ValueResponse>(
    queryKey,
    ([, p, n]) => fetchAPI<ValueResponse>(`/strategy/value?preset=${p}&top_n=${n}`)
  )

  const handleScreen = () => {
    setSubmitted(true)
    setQueryKey(['/strategy/value', preset, topN])
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold" style={{ color: 'var(--foreground)' }}>選股篩選</h1>
        <p className="text-sm mt-1" style={{ color: 'var(--muted-foreground)' }}>價值策略多條件選股</p>
      </div>

      {/* 策略選擇 */}
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
            開始篩選
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
      ) : data && data.stocks.length > 0 ? (
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
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ background: 'var(--secondary)' }}>
                  {['排名', '代號', '名稱', '現價', 'PE', 'PB', '殖利率%'].map(h => (
                    <th key={h} className="text-left py-2 px-4" style={{ color: 'var(--muted-foreground)' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.stocks.map((row, i) => (
                  <tr
                    key={row.stock_id}
                    style={{ borderBottom: '1px solid var(--border)' }}
                    className="hover:opacity-80"
                  >
                    <td className="py-2 px-4 tabular-nums" style={{ color: 'var(--muted-foreground)' }}>{i + 1}</td>
                    <td className="py-2 px-4 font-medium" style={{ color: 'var(--primary)' }}>{row.stock_id}</td>
                    <td className="py-2 px-4" style={{ color: 'var(--foreground)' }}>{row.name ?? '—'}</td>
                    <td className="py-2 px-4 tabular-nums" style={{ color: 'var(--foreground)' }}>{row.price.toFixed(2)}</td>
                    <td className="py-2 px-4 tabular-nums" style={{ color: 'var(--foreground)' }}>{row.pe_ratio.toFixed(1)}</td>
                    <td className="py-2 px-4 tabular-nums" style={{ color: 'var(--foreground)' }}>{row.pb_ratio.toFixed(2)}</td>
                    <td className="py-2 px-4 tabular-nums font-semibold" style={{ color: 'var(--primary)' }}>
                      {row.dividend_yield.toFixed(2)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
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
