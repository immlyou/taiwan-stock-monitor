'use client'

import { useState } from 'react'
import { fetchAPI } from '@/lib/api/client'
import { StockInput } from '@/components/shared/StockInput'

interface ParamRange {
  key: string
  label: string
  min: number
  max: number
  step: number
  unit: string
}

interface OptimizeResult {
  bestParams: Record<string, number>
  bestScore: number
  totalReturn: number
  sharpe: number
  maxDrawdown: number
  winRate: number
  tradeCount: number
  grid: Array<{
    params: Record<string, number>
    score: number
    totalReturn: number
    sharpe: number
  }>
}

const PARAM_RANGES: ParamRange[] = [
  { key: 'fastPeriod', label: '快線週期', min: 3, max: 20, step: 1, unit: '日' },
  { key: 'slowPeriod', label: '慢線週期', min: 10, max: 60, step: 5, unit: '日' },
  { key: 'rsiThreshold', label: 'RSI 閾值', min: 20, max: 40, step: 5, unit: '' },
  { key: 'stopLoss', label: '停損 %', min: 3, max: 15, step: 1, unit: '%' },
]

const STRATEGIES = [
  { key: 'ma_crossover', label: '均線交叉' },
  { key: 'rsi_reversal', label: 'RSI 反轉' },
  { key: 'breakout', label: '突破策略' },
]

export default function OptimizerPage() {
  const [strategy, setStrategy] = useState('ma_crossover')
  const [stockCode, setStockCode] = useState('')
  const [startDate, setStartDate] = useState('2022-01-01')
  const [endDate, setEndDate] = useState('2024-12-31')
  const [ranges, setRanges] = useState<Record<string, { min: number; max: number }>>({
    fastPeriod: { min: 3, max: 15 },
    slowPeriod: { min: 10, max: 40 },
    rsiThreshold: { min: 25, max: 35 },
    stopLoss: { min: 5, max: 10 },
  })
  const [result, setResult] = useState<OptimizeResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [progress, setProgress] = useState(0)

  const updateRange = (key: string, field: 'min' | 'max', value: number) => {
    setRanges(prev => ({ ...prev, [key]: { ...prev[key], [field]: value } }))
  }

  const estimateCount = () => {
    return PARAM_RANGES.reduce((total, p) => {
      const range = ranges[p.key]
      const count = Math.floor((range.max - range.min) / p.step) + 1
      return total * count
    }, 1)
  }

  const handleOptimize = async () => {
    if (!stockCode.trim()) {
      setError('請輸入股票代號')
      return
    }
    setLoading(true)
    setError('')
    setResult(null)
    setProgress(0)

    // 模擬進度
    const progressInterval = setInterval(() => {
      setProgress(prev => Math.min(prev + Math.random() * 15, 90))
    }, 500)

    try {
      const data = await fetchAPI<OptimizeResult>('/optimizer/run', {
        method: 'POST',
        body: JSON.stringify({ strategy, stockCode, startDate, endDate, ranges }),
      })
      setProgress(100)
      setResult(data)
    } catch {
      setError('優化失敗，請稍後再試')
    } finally {
      clearInterval(progressInterval)
      setLoading(false)
    }
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold" style={{ color: 'var(--foreground)' }}>參數優化</h1>
        <p className="text-sm mt-1" style={{ color: 'var(--muted-foreground)' }}>Grid Search 暴力窮舉最佳參數</p>
      </div>

      {/* 設定 */}
      <div
        className="rounded-lg p-4 mb-6"
        style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
      >
        <p className="text-sm font-medium mb-3" style={{ color: 'var(--foreground)' }}>基本設定</p>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
          <div>
            <label className="block text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>策略</label>
            <select
              value={strategy}
              onChange={(e) => setStrategy(e.target.value)}
              className="h-9 w-full rounded-md border px-3 text-sm"
              style={{ background: 'var(--background)', border: '1px solid var(--border)', color: 'var(--foreground)' }}
            >
              {STRATEGIES.map(s => <option key={s.key} value={s.key}>{s.label}</option>)}
            </select>
          </div>
          <div>
            <StockInput
              value={stockCode}
              onChange={setStockCode}
              label="股票代號"
              placeholder="例：2330 或 台積電"
            />
          </div>
          <div>
            <label className="block text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>開始日期</label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="h-9 w-full rounded-md border px-3 text-sm"
              style={{ background: 'var(--background)', border: '1px solid var(--border)', color: 'var(--foreground)' }}
            />
          </div>
          <div>
            <label className="block text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>結束日期</label>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="h-9 w-full rounded-md border px-3 text-sm"
              style={{ background: 'var(--background)', border: '1px solid var(--border)', color: 'var(--foreground)' }}
            />
          </div>
        </div>

        <p className="text-sm font-medium mb-3" style={{ color: 'var(--foreground)' }}>參數搜尋範圍</p>
        <div className="space-y-2">
          {PARAM_RANGES.map((p) => (
            <div key={p.key} className="flex items-center gap-3">
              <span className="w-24 text-sm" style={{ color: 'var(--foreground)' }}>{p.label}</span>
              <div className="flex items-center gap-2">
                <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>從</span>
                <input
                  type="number"
                  value={ranges[p.key].min}
                  onChange={(e) => updateRange(p.key, 'min', Number(e.target.value))}
                  min={p.min}
                  max={p.max}
                  step={p.step}
                  className="h-8 w-20 rounded border px-2 text-sm"
                  style={{ background: 'var(--background)', border: '1px solid var(--border)', color: 'var(--foreground)' }}
                />
                <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>到</span>
                <input
                  type="number"
                  value={ranges[p.key].max}
                  onChange={(e) => updateRange(p.key, 'max', Number(e.target.value))}
                  min={p.min}
                  max={p.max}
                  step={p.step}
                  className="h-8 w-20 rounded border px-2 text-sm"
                  style={{ background: 'var(--background)', border: '1px solid var(--border)', color: 'var(--foreground)' }}
                />
                <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>步長 {p.step} {p.unit}</span>
              </div>
            </div>
          ))}
        </div>

        <div className="mt-4 flex justify-between items-center">
          <p className="text-sm" style={{ color: 'var(--muted-foreground)' }}>
            預估測試組合數：<span className="font-semibold" style={{ color: 'var(--foreground)' }}>{estimateCount().toLocaleString()}</span> 組
          </p>
          <button
            onClick={handleOptimize}
            disabled={loading}
            className="h-9 px-6 rounded-md text-sm font-medium disabled:opacity-60"
            style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}
          >
            {loading ? '優化中...' : '執行 Grid Search'}
          </button>
        </div>

        {error && <p className="mt-2 text-sm" style={{ color: 'var(--destructive)' }}>{error}</p>}

        {/* 進度條 */}
        {loading && (
          <div className="mt-4">
            <div className="flex justify-between text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>
              <span>優化進度</span>
              <span>{progress.toFixed(0)}%</span>
            </div>
            <div className="w-full h-2 rounded-full overflow-hidden" style={{ background: 'var(--secondary)' }}>
              <div
                className="h-full rounded-full transition-all duration-500"
                style={{ width: `${progress}%`, background: 'var(--primary)' }}
              />
            </div>
          </div>
        )}
      </div>

      {/* 結果 */}
      {result && (
        <div className="space-y-4">
          {/* 最佳參數 */}
          <div
            className="rounded-lg p-4"
            style={{ background: 'var(--card)', border: '1px solid var(--border)', borderLeft: '4px solid var(--primary)' }}
          >
            <h3 className="text-sm font-semibold mb-3" style={{ color: 'var(--primary)' }}>最佳參數組合</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {Object.entries(result.bestParams).map(([key, value]) => {
                const paramDef = PARAM_RANGES.find(p => p.key === key)
                return (
                  <div key={key}>
                    <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
                      {paramDef?.label ?? key}
                    </p>
                    <p className="text-xl font-bold tabular-nums" style={{ color: 'var(--foreground)' }}>
                      {value} {paramDef?.unit}
                    </p>
                  </div>
                )
              })}
            </div>
          </div>

          {/* 績效 */}
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            {[
              { label: '最佳評分', value: result.bestScore.toFixed(2) },
              { label: '總報酬率', value: `${result.totalReturn > 0 ? '+' : ''}${result.totalReturn.toFixed(2)}%` },
              { label: 'Sharpe Ratio', value: result.sharpe.toFixed(2) },
              { label: '最大回撤', value: `${result.maxDrawdown.toFixed(2)}%` },
              { label: '勝率', value: `${result.winRate.toFixed(1)}%` },
              { label: '交易次數', value: String(result.tradeCount) },
            ].map(({ label, value }) => (
              <div
                key={label}
                className="rounded-lg p-4"
                style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
              >
                <p className="text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>{label}</p>
                <p className="text-xl font-bold tabular-nums" style={{ color: 'var(--foreground)' }}>{value}</p>
              </div>
            ))}
          </div>

          {/* Top 10 結果表格 */}
          {result.grid && result.grid.length > 0 && (
            <div
              className="rounded-lg overflow-hidden"
              style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
            >
              <div className="px-4 py-3 border-b" style={{ borderColor: 'var(--border)' }}>
                <h3 className="text-sm font-medium" style={{ color: 'var(--foreground)' }}>Top 10 參數組合</h3>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr style={{ background: 'var(--secondary)' }}>
                      <th className="text-left py-2 px-4" style={{ color: 'var(--muted-foreground)' }}>排名</th>
                      {Object.keys(result.grid[0].params).map(k => (
                        <th key={k} className="text-left py-2 px-4" style={{ color: 'var(--muted-foreground)' }}>
                          {PARAM_RANGES.find(p => p.key === k)?.label ?? k}
                        </th>
                      ))}
                      <th className="text-left py-2 px-4" style={{ color: 'var(--muted-foreground)' }}>評分</th>
                      <th className="text-left py-2 px-4" style={{ color: 'var(--muted-foreground)' }}>總報酬</th>
                      <th className="text-left py-2 px-4" style={{ color: 'var(--muted-foreground)' }}>Sharpe</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.grid.slice(0, 10).map((row, i) => (
                      <tr
                        key={i}
                        style={{
                          borderBottom: '1px solid var(--border)',
                          background: i === 0 ? 'rgba(59,130,246,0.08)' : undefined,
                        }}
                      >
                        <td className="py-2 px-4 tabular-nums" style={{ color: 'var(--muted-foreground)' }}>{i + 1}</td>
                        {Object.values(row.params).map((v, j) => (
                          <td key={j} className="py-2 px-4 tabular-nums" style={{ color: 'var(--foreground)' }}>{v}</td>
                        ))}
                        <td className="py-2 px-4 tabular-nums font-semibold" style={{ color: 'var(--primary)' }}>
                          {row.score.toFixed(2)}
                        </td>
                        <td
                          className="py-2 px-4 tabular-nums"
                          style={{ color: row.totalReturn >= 0 ? 'var(--stock-up)' : 'var(--stock-down)' }}
                        >
                          {row.totalReturn > 0 ? '+' : ''}{row.totalReturn.toFixed(2)}%
                        </td>
                        <td className="py-2 px-4 tabular-nums" style={{ color: 'var(--foreground)' }}>
                          {row.sharpe.toFixed(2)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
