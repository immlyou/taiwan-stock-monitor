'use client'

import { useState } from 'react'
import useSWR from 'swr'
import { fetchAPI } from '@/lib/api/client'
import { getChangeColorVar } from '@/lib/utils/format'

interface FactorWeight {
  key: string
  label: string
  weight: number
  description: string
}

interface AiPickResult {
  code: string
  name: string
  close: number
  changePercent: number
  aiScore: number
  factorScores: {
    value: number
    growth: number
    momentum: number
    quality: number
    sentiment: number
  }
  recommendation: 'strong_buy' | 'buy' | 'hold' | 'sell'
  targetPrice?: number
}

const DEFAULT_FACTORS: FactorWeight[] = [
  { key: 'value', label: '價值因子', weight: 25, description: 'PE、PB、殖利率' },
  { key: 'growth', label: '成長因子', weight: 25, description: '營收成長、EPS 成長' },
  { key: 'momentum', label: '動能因子', weight: 20, description: '近期漲幅、強弱度' },
  { key: 'quality', label: '品質因子', weight: 20, description: 'ROE、毛利率、負債比' },
  { key: 'sentiment', label: '情緒因子', weight: 10, description: '法人動向、融資比例' },
]

const REC_LABELS: Record<string, { label: string; color: string }> = {
  strong_buy: { label: '強力買進', color: 'var(--stock-up)' },
  buy: { label: '買進', color: '#22c55e' },
  hold: { label: '持有', color: 'var(--stock-flat)' },
  sell: { label: '賣出', color: 'var(--stock-down)' },
}

export default function AiPickPage() {
  const [factors, setFactors] = useState<FactorWeight[]>(DEFAULT_FACTORS)
  const [submitted, setSubmitted] = useState(false)
  const [submitWeights, setSubmitWeights] = useState<Record<string, number>>({})

  const totalWeight = factors.reduce((s, f) => s + f.weight, 0)

  const { data, isLoading, error } = useSWR<AiPickResult[]>(
    submitted ? ['/strategy/ai-pick', submitWeights] : null,
    ([url, w]) => fetchAPI<AiPickResult[]>(url, { method: 'POST', body: JSON.stringify({ weights: w }) })
  )

  const handleRun = () => {
    if (totalWeight !== 100) return
    const weights: Record<string, number> = {}
    factors.forEach(f => { weights[f.key] = f.weight })
    setSubmitWeights(weights)
    setSubmitted(true)
  }

  const updateWeight = (key: string, value: number) => {
    setFactors(prev => prev.map(f => f.key === key ? { ...f, weight: Math.max(0, Math.min(100, value)) } : f))
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold" style={{ color: 'var(--foreground)' }}>AI 智慧選股</h1>
        <p className="text-sm mt-1" style={{ color: 'var(--muted-foreground)' }}>多因子模型 AI 選股排行</p>
      </div>

      {/* 因子權重設定 */}
      <div
        className="rounded-lg p-4 mb-6"
        style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
      >
        <div className="flex justify-between items-center mb-3">
          <p className="text-sm font-medium" style={{ color: 'var(--foreground)' }}>因子權重設定</p>
          <span
            className="text-sm font-semibold"
            style={{ color: totalWeight === 100 ? 'var(--stock-down)' : 'var(--destructive)' }}
          >
            總計：{totalWeight}%（需為 100%）
          </span>
        </div>
        <div className="space-y-3">
          {factors.map((factor) => (
            <div key={factor.key} className="flex items-center gap-4">
              <div className="w-28">
                <p className="text-sm font-medium" style={{ color: 'var(--foreground)' }}>{factor.label}</p>
                <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>{factor.description}</p>
              </div>
              <input
                type="range"
                min={0}
                max={60}
                step={5}
                value={factor.weight}
                onChange={(e) => updateWeight(factor.key, Number(e.target.value))}
                className="flex-1"
                style={{ accentColor: 'var(--primary)' }}
              />
              <div className="flex items-center gap-1 w-16">
                <input
                  type="number"
                  min={0}
                  max={100}
                  value={factor.weight}
                  onChange={(e) => updateWeight(factor.key, Number(e.target.value))}
                  className="h-8 w-14 rounded-md border px-2 text-sm text-right tabular-nums"
                  style={{ background: 'var(--background)', border: '1px solid var(--border)', color: 'var(--foreground)' }}
                />
                <span className="text-sm" style={{ color: 'var(--muted-foreground)' }}>%</span>
              </div>
              {/* 進度條 */}
              <div
                className="w-24 h-2 rounded-full overflow-hidden"
                style={{ background: 'var(--secondary)' }}
              >
                <div
                  className="h-full rounded-full transition-all"
                  style={{ width: `${factor.weight}%`, background: 'var(--primary)' }}
                />
              </div>
            </div>
          ))}
        </div>
        <div className="mt-4 flex justify-end">
          <button
            onClick={handleRun}
            disabled={totalWeight !== 100}
            className="h-9 px-6 rounded-md text-sm font-medium disabled:opacity-50"
            style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}
          >
            執行 AI 選股
          </button>
        </div>
      </div>

      {/* 結果 */}
      {!submitted ? null : error ? (
        <div className="rounded-lg p-6 text-center" style={{ background: 'var(--card)', border: '1px solid var(--border)' }}>
          <p style={{ color: 'var(--destructive)' }}>AI 選股失敗</p>
        </div>
      ) : isLoading ? (
        <div className="rounded-lg p-8 text-center" style={{ background: 'var(--card)', border: '1px solid var(--border)' }}>
          <p style={{ color: 'var(--muted-foreground)' }}>AI 模型運算中...</p>
        </div>
      ) : data && data.length > 0 ? (
        <div
          className="rounded-lg overflow-hidden"
          style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
        >
          <div className="px-4 py-3 border-b" style={{ borderColor: 'var(--border)' }}>
            <h3 className="text-sm font-medium" style={{ color: 'var(--foreground)' }}>
              AI 選股排行 — 共 {data.length} 支
            </h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ background: 'var(--secondary)' }}>
                  {['排名', '代號', '名稱', '現價', '漲跌%', 'AI 評分', '價值', '成長', '動能', '品質', '情緒', '建議', '目標價'].map(h => (
                    <th key={h} className="text-left py-2 px-3" style={{ color: 'var(--muted-foreground)', fontSize: '0.75rem' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.map((row, i) => {
                  const rec = REC_LABELS[row.recommendation] ?? { label: '—', color: 'var(--foreground)' }
                  return (
                    <tr key={row.code} style={{ borderBottom: '1px solid var(--border)' }}>
                      <td className="py-2 px-3 tabular-nums" style={{ color: 'var(--muted-foreground)' }}>{i + 1}</td>
                      <td className="py-2 px-3 font-medium" style={{ color: 'var(--primary)' }}>{row.code}</td>
                      <td className="py-2 px-3" style={{ color: 'var(--foreground)' }}>{row.name}</td>
                      <td className="py-2 px-3 tabular-nums" style={{ color: 'var(--foreground)' }}>{row.close.toFixed(2)}</td>
                      <td className="py-2 px-3 tabular-nums" style={{ color: getChangeColorVar(row.changePercent) }}>
                        {row.changePercent > 0 ? '+' : ''}{row.changePercent.toFixed(2)}%
                      </td>
                      <td className="py-2 px-3 tabular-nums font-bold" style={{ color: 'var(--primary)' }}>
                        {row.aiScore.toFixed(1)}
                      </td>
                      {(['value', 'growth', 'momentum', 'quality', 'sentiment'] as const).map(k => (
                        <td key={k} className="py-2 px-3 tabular-nums" style={{ color: 'var(--foreground)' }}>
                          {row.factorScores[k].toFixed(0)}
                        </td>
                      ))}
                      <td className="py-2 px-3 font-semibold text-xs" style={{ color: rec.color }}>
                        {rec.label}
                      </td>
                      <td className="py-2 px-3 tabular-nums" style={{ color: 'var(--muted-foreground)' }}>
                        {row.targetPrice ? row.targetPrice.toFixed(2) : '—'}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      ) : data ? (
        <div className="rounded-lg p-6 text-center" style={{ background: 'var(--card)', border: '1px solid var(--border)' }}>
          <p style={{ color: 'var(--muted-foreground)' }}>暫無 AI 選股結果</p>
        </div>
      ) : null}
    </div>
  )
}
