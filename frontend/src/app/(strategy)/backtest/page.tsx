'use client'

import { useState } from 'react'
import { fetchAPI } from '@/lib/api/client'
import { KpiCard } from '@/components/shared/KpiCard'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine
} from 'recharts'

interface BacktestMetrics {
  total_return: number
  annualized_return: number
  volatility: number
  sharpe_ratio: number
  sortino_ratio: number
  max_drawdown: number
  win_rate: number
  total_trades: number
  profit_factor: number
  calmar_ratio: number
}

interface PortfolioValue {
  date: string
  value: number
}

interface BenchmarkComparison {
  excess_return: number
  beta: number
  alpha: number
  information_ratio: number
  correlation: number
  tracking_error: number
}

interface BacktestResult {
  strategy: string
  preset: string
  config: {
    initial_capital: number
    rebalance_freq: string
    max_stocks: number
    weight_method: string
    start_date: string
    end_date: string
  }
  metrics: BacktestMetrics
  portfolio_values: PortfolioValue[]
  benchmark_comparison: BenchmarkComparison
}

const STRATEGIES = [
  { key: 'value', label: '價值投資' },
  { key: 'growth', label: '成長選股' },
  { key: 'momentum', label: '動能選股' },
]

export default function BacktestPage() {
  const [form, setForm] = useState({
    strategy: 'value',
    startDate: '2024-01-01',
    endDate: '2024-12-31',
    initialCapital: 1000000,
  })
  const [result, setResult] = useState<BacktestResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleRun = async () => {
    setLoading(true)
    setError('')
    setResult(null)
    try {
      const data = await fetchAPI<BacktestResult>('/backtest/run', {
        method: 'POST',
        body: JSON.stringify({
          strategy: form.strategy,
          preset: 'standard',
          start_date: form.startDate,
          end_date: form.endDate,
          initial_capital: form.initialCapital,
        }),
      })
      setResult(data)
    } catch {
      setError('回測執行失敗，請稍後再試')
    } finally {
      setLoading(false)
    }
  }

  const updateForm = (key: string, value: string | number) => {
    setForm(prev => ({ ...prev, [key]: value }))
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold" style={{ color: 'var(--foreground)' }}>回測分析</h1>
        <p className="text-sm mt-1" style={{ color: 'var(--muted-foreground)' }}>策略歷史回測與績效驗證</p>
      </div>

      {/* 設定面板 */}
      <div
        className="rounded-lg p-4 mb-6"
        style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
      >
        <p className="text-sm font-medium mb-3" style={{ color: 'var(--foreground)' }}>回測設定</p>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div>
            <label className="block text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>策略</label>
            <select
              value={form.strategy}
              onChange={(e) => updateForm('strategy', e.target.value)}
              className="h-9 w-full rounded-md border px-3 text-sm"
              style={{ background: 'var(--background)', border: '1px solid var(--border)', color: 'var(--foreground)' }}
            >
              {STRATEGIES.map(s => (
                <option key={s.key} value={s.key}>{s.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>開始日期</label>
            <input
              type="date"
              value={form.startDate}
              onChange={(e) => updateForm('startDate', e.target.value)}
              className="h-9 w-full rounded-md border px-3 text-sm"
              style={{ background: 'var(--background)', border: '1px solid var(--border)', color: 'var(--foreground)' }}
            />
          </div>
          <div>
            <label className="block text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>結束日期</label>
            <input
              type="date"
              value={form.endDate}
              onChange={(e) => updateForm('endDate', e.target.value)}
              className="h-9 w-full rounded-md border px-3 text-sm"
              style={{ background: 'var(--background)', border: '1px solid var(--border)', color: 'var(--foreground)' }}
            />
          </div>
          <div>
            <label className="block text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>初始資金（元）</label>
            <input
              type="number"
              value={form.initialCapital}
              onChange={(e) => updateForm('initialCapital', Number(e.target.value))}
              className="h-9 w-full rounded-md border px-3 text-sm"
              style={{ background: 'var(--background)', border: '1px solid var(--border)', color: 'var(--foreground)' }}
            />
          </div>
        </div>
        {error && (
          <p className="mt-2 text-sm" style={{ color: 'var(--destructive)' }}>{error}</p>
        )}
        <div className="mt-4 flex justify-end">
          <button
            onClick={handleRun}
            disabled={loading}
            className="h-9 px-6 rounded-md text-sm font-medium disabled:opacity-60"
            style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}
          >
            {loading ? '回測執行中...' : '執行回測'}
          </button>
        </div>
      </div>

      {/* 結果 */}
      {result && (
        <div className="space-y-4">
          {/* KPI */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <KpiCard
              title="總報酬率"
              value={`${result.metrics.total_return > 0 ? '+' : ''}${result.metrics.total_return.toFixed(2)}%`}
              accentColor={result.metrics.total_return >= 0 ? 'var(--stock-up)' : 'var(--stock-down)'}
            />
            <KpiCard
              title="年化報酬率"
              value={`${result.metrics.annualized_return > 0 ? '+' : ''}${result.metrics.annualized_return.toFixed(2)}%`}
              accentColor="var(--primary)"
            />
            <KpiCard
              title="最大回撤"
              value={`${result.metrics.max_drawdown.toFixed(2)}%`}
              accentColor="var(--destructive)"
            />
            <KpiCard
              title="Sharpe Ratio"
              value={result.metrics.sharpe_ratio.toFixed(2)}
              accentColor="#8b5cf6"
            />
            <KpiCard
              title="勝率"
              value={`${result.metrics.win_rate.toFixed(1)}%`}
              accentColor="#f59e0b"
            />
            <KpiCard
              title="交易次數"
              value={String(result.metrics.total_trades)}
              accentColor="var(--muted-foreground)"
            />
            <KpiCard
              title="獲利因子"
              value={result.metrics.profit_factor.toFixed(2)}
              accentColor="var(--stock-up)"
            />
            <KpiCard
              title="Calmar Ratio"
              value={result.metrics.calmar_ratio.toFixed(2)}
              accentColor="#f97316"
            />
          </div>

          {/* 淨值走勢 */}
          <div
            className="rounded-lg p-4"
            style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
          >
            <h3 className="text-sm font-medium mb-3" style={{ color: 'var(--muted-foreground)' }}>
              策略淨值走勢（{result.config.start_date} ~ {result.config.end_date}）
            </h3>
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={result.portfolio_values}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis
                  dataKey="date"
                  tick={{ fill: 'var(--muted-foreground)', fontSize: 10 }}
                  tickFormatter={(v: string) => v.slice(5)}
                  interval={Math.floor(result.portfolio_values.length / 8)}
                />
                <YAxis
                  tick={{ fill: 'var(--muted-foreground)', fontSize: 10 }}
                  tickFormatter={(v: number) => `${(v / 1e4).toFixed(0)}萬`}
                />
                <Tooltip
                  contentStyle={{ background: 'var(--card)', border: '1px solid var(--border)', color: 'var(--foreground)' }}
                  // eslint-disable-next-line @typescript-eslint/no-explicit-any
                  formatter={(v: any) => [`${(Number(v ?? 0) / 1e4).toFixed(2)} 萬`, '淨值']}
                />
                <ReferenceLine y={result.config.initial_capital} stroke="var(--border)" strokeDasharray="4 2" />
                <Line type="monotone" dataKey="value" stroke="var(--primary)" dot={false} strokeWidth={2} name="策略淨值" />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* 基準對比 */}
          <div
            className="rounded-lg p-4"
            style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
          >
            <h3 className="text-sm font-medium mb-3" style={{ color: 'var(--muted-foreground)' }}>基準比較</h3>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
              {[
                { label: '超額報酬', value: `${result.benchmark_comparison.excess_return.toFixed(2)}%` },
                { label: 'Alpha', value: result.benchmark_comparison.alpha.toFixed(2) },
                { label: 'Beta', value: result.benchmark_comparison.beta.toFixed(2) },
                { label: 'Information Ratio', value: result.benchmark_comparison.information_ratio.toFixed(2) },
                { label: '相關係數', value: result.benchmark_comparison.correlation.toFixed(2) },
                { label: 'Tracking Error', value: `${result.benchmark_comparison.tracking_error.toFixed(2)}%` },
              ].map(({ label, value }) => (
                <div key={label}>
                  <p className="text-xs mb-0.5" style={{ color: 'var(--muted-foreground)' }}>{label}</p>
                  <p className="font-semibold tabular-nums" style={{ color: 'var(--foreground)' }}>{value}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
