'use client'

import { useState } from 'react'
import useSWR from 'swr'
import { fetchAPI } from '@/lib/api/client'
import { getChangeColorVar } from '@/lib/utils/format'

interface ScreenerResult {
  code: string
  name: string
  close: number
  changePercent: number
  pe?: number
  pb?: number
  roe?: number
  dividendYield?: number
  score: number
}

type StrategyType = 'value' | 'growth' | 'momentum' | 'composite'

interface ScreenerParams {
  strategy: StrategyType
  minPe?: number
  maxPe?: number
  minRoe?: number
  minDividendYield?: number
  minChangePercent?: number
  maxChangePercent?: number
  limit: number
}

const STRATEGIES: { key: StrategyType; label: string; desc: string }[] = [
  { key: 'value', label: '價值選股', desc: 'PE 低、PB 低、高殖利率' },
  { key: 'growth', label: '成長選股', desc: '高 ROE、營收成長' },
  { key: 'momentum', label: '動能選股', desc: '近期漲幅強、成交量放大' },
  { key: 'composite', label: '綜合評分', desc: '多因子加權綜合排名' },
]

export default function ScreenerPage() {
  const [strategy, setStrategy] = useState<StrategyType>('composite')
  const [params, setParams] = useState<ScreenerParams>({
    strategy: 'composite',
    minPe: undefined,
    maxPe: 20,
    minRoe: 10,
    minDividendYield: undefined,
    limit: 20,
  })
  const [submitted, setSubmitted] = useState(false)
  const [submitParams, setSubmitParams] = useState<ScreenerParams | null>(null)

  const { data, isLoading, error } = useSWR<ScreenerResult[]>(
    submitted && submitParams ? ['/screener', submitParams] : null,
    ([url, p]) => fetchAPI<ScreenerResult[]>(url, { method: 'POST', body: JSON.stringify(p) })
  )

  const handleScreen = () => {
    const p = { ...params, strategy }
    setSubmitParams(p)
    setSubmitted(true)
  }

  const updateParam = (key: keyof ScreenerParams, value: number | string | undefined) => {
    setParams(prev => ({ ...prev, [key]: value === '' ? undefined : value }))
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold" style={{ color: 'var(--foreground)' }}>選股篩選</h1>
        <p className="text-sm mt-1" style={{ color: 'var(--muted-foreground)' }}>多策略條件選股</p>
      </div>

      {/* 策略選擇 */}
      <div
        className="rounded-lg p-4 mb-4"
        style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
      >
        <p className="text-xs mb-3 font-medium" style={{ color: 'var(--muted-foreground)' }}>策略類型</p>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
          {STRATEGIES.map((s) => (
            <button
              key={s.key}
              onClick={() => setStrategy(s.key)}
              className="p-3 rounded-lg text-left transition-colors"
              style={{
                background: strategy === s.key ? 'var(--primary)' : 'var(--secondary)',
                color: strategy === s.key ? 'var(--primary-foreground)' : 'var(--foreground)',
                border: strategy === s.key ? '2px solid var(--primary)' : '2px solid transparent',
              }}
            >
              <p className="text-sm font-semibold">{s.label}</p>
              <p
                className="text-xs mt-0.5"
                style={{ color: strategy === s.key ? 'rgba(255,255,255,0.8)' : 'var(--muted-foreground)' }}
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
        <p className="text-xs mb-3 font-medium" style={{ color: 'var(--muted-foreground)' }}>篩選條件</p>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[
            { key: 'minPe' as const, label: 'PE 最小值' },
            { key: 'maxPe' as const, label: 'PE 最大值' },
            { key: 'minRoe' as const, label: 'ROE 最小 %' },
            { key: 'minDividendYield' as const, label: '最低殖利率 %' },
          ].map(({ key, label }) => (
            <div key={key}>
              <label className="block text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>{label}</label>
              <input
                type="number"
                value={params[key] ?? ''}
                onChange={(e) => updateParam(key, e.target.value === '' ? undefined : Number(e.target.value))}
                placeholder="不限"
                className="h-9 w-full rounded-md border px-3 text-sm"
                style={{ background: 'var(--background)', border: '1px solid var(--border)', color: 'var(--foreground)' }}
              />
            </div>
          ))}
          <div>
            <label className="block text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>結果數量</label>
            <select
              value={params.limit}
              onChange={(e) => updateParam('limit', Number(e.target.value))}
              className="h-9 w-full rounded-md border px-3 text-sm"
              style={{ background: 'var(--background)', border: '1px solid var(--border)', color: 'var(--foreground)' }}
            >
              {[10, 20, 30, 50].map(n => (
                <option key={n} value={n}>{n} 支</option>
              ))}
            </select>
          </div>
        </div>
        <div className="mt-4 flex justify-end">
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
          <p style={{ color: 'var(--destructive)' }}>篩選失敗</p>
        </div>
      ) : isLoading ? (
        <div
          className="rounded-lg p-8 text-center"
          style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
        >
          <p style={{ color: 'var(--muted-foreground)' }}>篩選中...</p>
        </div>
      ) : data && data.length > 0 ? (
        <div
          className="rounded-lg overflow-hidden"
          style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
        >
          <div className="px-4 py-3 flex justify-between items-center border-b" style={{ borderColor: 'var(--border)' }}>
            <h3 className="text-sm font-medium" style={{ color: 'var(--foreground)' }}>
              篩選結果 — 共 {data.length} 支
            </h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ background: 'var(--secondary)' }}>
                  {['排名', '代號', '名稱', '現價', '漲跌%', 'PE', 'PB', 'ROE%', '殖利率%', '評分'].map(h => (
                    <th key={h} className="text-left py-2 px-4" style={{ color: 'var(--muted-foreground)' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.map((row, i) => (
                  <tr
                    key={row.code}
                    style={{ borderBottom: '1px solid var(--border)' }}
                    className="hover:opacity-80"
                  >
                    <td className="py-2 px-4 tabular-nums" style={{ color: 'var(--muted-foreground)' }}>{i + 1}</td>
                    <td className="py-2 px-4 font-medium" style={{ color: 'var(--primary)' }}>{row.code}</td>
                    <td className="py-2 px-4" style={{ color: 'var(--foreground)' }}>{row.name}</td>
                    <td className="py-2 px-4 tabular-nums" style={{ color: 'var(--foreground)' }}>{row.close.toFixed(2)}</td>
                    <td className="py-2 px-4 tabular-nums" style={{ color: getChangeColorVar(row.changePercent) }}>
                      {row.changePercent > 0 ? '+' : ''}{row.changePercent.toFixed(2)}%
                    </td>
                    <td className="py-2 px-4 tabular-nums" style={{ color: 'var(--foreground)' }}>{row.pe?.toFixed(1) ?? '—'}</td>
                    <td className="py-2 px-4 tabular-nums" style={{ color: 'var(--foreground)' }}>{row.pb?.toFixed(2) ?? '—'}</td>
                    <td className="py-2 px-4 tabular-nums" style={{ color: 'var(--foreground)' }}>{row.roe?.toFixed(1) ?? '—'}</td>
                    <td className="py-2 px-4 tabular-nums" style={{ color: 'var(--foreground)' }}>{row.dividendYield?.toFixed(2) ?? '—'}</td>
                    <td className="py-2 px-4 tabular-nums font-semibold" style={{ color: 'var(--primary)' }}>
                      {row.score.toFixed(1)}
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
