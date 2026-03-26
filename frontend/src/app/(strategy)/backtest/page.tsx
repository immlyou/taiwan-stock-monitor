'use client'

import { useState } from 'react'
import { fetchAPI } from '@/lib/api/client'
import { KpiCard } from '@/components/shared/KpiCard'
import { getChangeColorVar } from '@/lib/utils/format'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine
} from 'recharts'

interface BacktestResult {
  summary: {
    totalReturn: number
    annualReturn: number
    maxDrawdown: number
    sharpe: number
    winRate: number
    tradeCount: number
    startDate: string
    endDate: string
    initialCapital: number
    finalCapital: number
  }
  navHistory: Array<{ date: string; nav: number; benchmark?: number }>
  trades: Array<{
    date: string
    code: string
    name: string
    action: 'buy' | 'sell'
    price: number
    shares: number
    pnl?: number
  }>
}

const STRATEGIES = [
  { key: 'ma_crossover', label: '均線交叉' },
  { key: 'rsi_reversal', label: 'RSI 反轉' },
  { key: 'breakout', label: '突破策略' },
  { key: 'value_investing', label: '價值投資' },
]

export default function BacktestPage() {
  const [form, setForm] = useState({
    strategy: 'ma_crossover',
    stockCode: '',
    startDate: '2023-01-01',
    endDate: '2024-12-31',
    initialCapital: 1000000,
    fastPeriod: 5,
    slowPeriod: 20,
  })
  const [result, setResult] = useState<BacktestResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleRun = async () => {
    if (!form.stockCode.trim()) {
      setError('請輸入股票代號')
      return
    }
    setLoading(true)
    setError('')
    setResult(null)
    try {
      const data = await fetchAPI<BacktestResult>('/backtest/run', {
        method: 'POST',
        body: JSON.stringify(form),
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
            <label className="block text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>股票代號</label>
            <input
              type="text"
              value={form.stockCode}
              onChange={(e) => updateForm('stockCode', e.target.value.toUpperCase())}
              placeholder="例：2330"
              className="h-9 w-full rounded-md border px-3 text-sm"
              style={{ background: 'var(--background)', border: '1px solid var(--border)', color: 'var(--foreground)' }}
            />
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
          <div>
            <label className="block text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>快線週期</label>
            <input
              type="number"
              value={form.fastPeriod}
              onChange={(e) => updateForm('fastPeriod', Number(e.target.value))}
              className="h-9 w-full rounded-md border px-3 text-sm"
              style={{ background: 'var(--background)', border: '1px solid var(--border)', color: 'var(--foreground)' }}
            />
          </div>
          <div>
            <label className="block text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>慢線週期</label>
            <input
              type="number"
              value={form.slowPeriod}
              onChange={(e) => updateForm('slowPeriod', Number(e.target.value))}
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
              value={`${result.summary.totalReturn > 0 ? '+' : ''}${result.summary.totalReturn.toFixed(2)}%`}
              accentColor={result.summary.totalReturn >= 0 ? 'var(--stock-up)' : 'var(--stock-down)'}
            />
            <KpiCard
              title="年化報酬率"
              value={`${result.summary.annualReturn > 0 ? '+' : ''}${result.summary.annualReturn.toFixed(2)}%`}
              accentColor="var(--primary)"
            />
            <KpiCard
              title="最大回撤"
              value={`${result.summary.maxDrawdown.toFixed(2)}%`}
              accentColor="var(--destructive)"
            />
            <KpiCard
              title="Sharpe Ratio"
              value={result.summary.sharpe.toFixed(2)}
              accentColor="#8b5cf6"
            />
            <KpiCard
              title="勝率"
              value={`${result.summary.winRate.toFixed(1)}%`}
              accentColor="#f59e0b"
            />
            <KpiCard
              title="交易次數"
              value={String(result.summary.tradeCount)}
              accentColor="var(--muted-foreground)"
            />
            <KpiCard
              title="期末資金"
              value={`${(result.summary.finalCapital / 1e4).toFixed(1)} 萬`}
              subValue={`初始 ${(result.summary.initialCapital / 1e4).toFixed(0)} 萬`}
              accentColor="var(--stock-down)"
            />
          </div>

          {/* 淨值走勢 */}
          <div
            className="rounded-lg p-4"
            style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
          >
            <h3 className="text-sm font-medium mb-3" style={{ color: 'var(--muted-foreground)' }}>策略淨值走勢</h3>
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={result.navHistory}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis dataKey="date" tick={{ fill: 'var(--muted-foreground)', fontSize: 10 }} />
                <YAxis tick={{ fill: 'var(--muted-foreground)', fontSize: 10 }} />
                <Tooltip contentStyle={{ background: 'var(--card)', border: '1px solid var(--border)', color: 'var(--foreground)' }} />
                <ReferenceLine y={result.summary.initialCapital} stroke="var(--border)" strokeDasharray="4 2" />
                <Line type="monotone" dataKey="nav" stroke="var(--primary)" dot={false} strokeWidth={2} name="策略淨值" />
                {result.navHistory[0]?.benchmark !== undefined && (
                  <Line type="monotone" dataKey="benchmark" stroke="var(--muted-foreground)" dot={false} strokeWidth={1.5} strokeDasharray="4 2" name="指數基準" />
                )}
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* 交易記錄 */}
          <div
            className="rounded-lg overflow-hidden"
            style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
          >
            <div className="px-4 py-3 border-b" style={{ borderColor: 'var(--border)' }}>
              <h3 className="text-sm font-medium" style={{ color: 'var(--foreground)' }}>交易記錄</h3>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr style={{ background: 'var(--secondary)' }}>
                    {['日期', '代號', '名稱', '操作', '價格', '張數', '損益'].map(h => (
                      <th key={h} className="text-left py-2 px-4" style={{ color: 'var(--muted-foreground)' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {result.trades.slice(0, 50).map((t, i) => (
                    <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                      <td className="py-2 px-4 tabular-nums" style={{ color: 'var(--muted-foreground)' }}>{t.date}</td>
                      <td className="py-2 px-4" style={{ color: 'var(--primary)' }}>{t.code}</td>
                      <td className="py-2 px-4" style={{ color: 'var(--foreground)' }}>{t.name}</td>
                      <td
                        className="py-2 px-4 font-medium"
                        style={{ color: t.action === 'buy' ? 'var(--stock-up)' : 'var(--stock-down)' }}
                      >
                        {t.action === 'buy' ? '買進' : '賣出'}
                      </td>
                      <td className="py-2 px-4 tabular-nums" style={{ color: 'var(--foreground)' }}>{t.price.toFixed(2)}</td>
                      <td className="py-2 px-4 tabular-nums" style={{ color: 'var(--foreground)' }}>{t.shares}</td>
                      <td
                        className="py-2 px-4 tabular-nums font-medium"
                        style={{ color: t.pnl != null ? getChangeColorVar(t.pnl) : 'var(--muted-foreground)' }}
                      >
                        {t.pnl != null ? `${t.pnl > 0 ? '+' : ''}${t.pnl.toLocaleString()}` : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
