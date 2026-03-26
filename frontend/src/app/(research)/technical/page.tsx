'use client'

import { useState } from 'react'
import useSWR from 'swr'
import { fetchAPI } from '@/lib/api/client'
import {
  ComposedChart, Line, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend
} from 'recharts'

interface TechnicalChartData {
  date: string
  open: number
  high: number
  low: number
  close: number
  volume: number
  ma5?: number
  ma20?: number
  macd?: number
  macdSignal?: number
  macdHist?: number
  kdK?: number
  kdD?: number
  rsi?: number
  bollUpper?: number
  bollMiddle?: number
  bollLower?: number
}

type Indicator = 'macd' | 'kd' | 'rsi' | 'boll'

const PERIODS = [
  { label: '1 個月', value: '1m' },
  { label: '3 個月', value: '3m' },
  { label: '6 個月', value: '6m' },
  { label: '1 年', value: '1y' },
]

const INDICATORS: { key: Indicator; label: string }[] = [
  { key: 'macd', label: 'MACD' },
  { key: 'kd', label: 'KD' },
  { key: 'rsi', label: 'RSI' },
  { key: 'boll', label: '布林通道' },
]

export default function TechnicalPage() {
  const [stockCode, setStockCode] = useState('')
  const [inputCode, setInputCode] = useState('')
  const [period, setPeriod] = useState('3m')
  const [activeIndicators, setActiveIndicators] = useState<Indicator[]>(['macd'])

  const { data: chartData, isLoading, error } = useSWR<TechnicalChartData[]>(
    stockCode ? `/stocks/${stockCode}/technical-chart?period=${period}` : null,
    fetchAPI
  )

  const toggleIndicator = (ind: Indicator) => {
    setActiveIndicators(prev =>
      prev.includes(ind) ? prev.filter(i => i !== ind) : [...prev, ind]
    )
  }

  const handleSearch = () => {
    if (inputCode.trim()) {
      setStockCode(inputCode.trim().toUpperCase())
    }
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold" style={{ color: 'var(--foreground)' }}>技術分析</h1>
        <p className="text-sm mt-1" style={{ color: 'var(--muted-foreground)' }}>OHLCV 圖表與技術指標</p>
      </div>

      {/* 控制列 */}
      <div
        className="rounded-lg p-4 mb-6 flex flex-wrap gap-3 items-end"
        style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
      >
        <div className="flex-1 min-w-48">
          <label className="block text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>股票代號</label>
          <div className="flex gap-2">
            <input
              type="text"
              value={inputCode}
              onChange={(e) => setInputCode(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              placeholder="例：2330"
              className="flex-1 h-9 rounded-md border px-3 text-sm"
              style={{
                background: 'var(--background)',
                border: '1px solid var(--border)',
                color: 'var(--foreground)',
              }}
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
          <label className="block text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>期間</label>
          <div className="flex gap-1">
            {PERIODS.map((p) => (
              <button
                key={p.value}
                onClick={() => setPeriod(p.value)}
                className="h-9 px-3 rounded-md text-sm font-medium transition-colors"
                style={{
                  background: period === p.value ? 'var(--primary)' : 'var(--secondary)',
                  color: period === p.value ? 'var(--primary-foreground)' : 'var(--foreground)',
                }}
              >
                {p.label}
              </button>
            ))}
          </div>
        </div>

        <div>
          <label className="block text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>指標</label>
          <div className="flex gap-2">
            {INDICATORS.map((ind) => (
              <label key={ind.key} className="flex items-center gap-1.5 cursor-pointer">
                <input
                  type="checkbox"
                  checked={activeIndicators.includes(ind.key)}
                  onChange={() => toggleIndicator(ind.key)}
                  className="rounded"
                  style={{ accentColor: 'var(--primary)' }}
                />
                <span className="text-sm" style={{ color: 'var(--foreground)' }}>{ind.label}</span>
              </label>
            ))}
          </div>
        </div>
      </div>

      {/* 圖表區 */}
      {!stockCode ? (
        <div
          className="rounded-lg p-12 text-center"
          style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
        >
          <p className="text-lg" style={{ color: 'var(--muted-foreground)' }}>請輸入股票代號開始分析</p>
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
          <p style={{ color: 'var(--muted-foreground)' }}>載入 {stockCode} 技術分析中...</p>
        </div>
      ) : chartData && chartData.length > 0 ? (
        <div className="space-y-4">
          {/* 價格圖 */}
          <div
            className="rounded-lg p-4"
            style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
          >
            <h3 className="text-sm font-medium mb-3" style={{ color: 'var(--muted-foreground)' }}>
              {stockCode} 收盤價走勢
            </h3>
            <ResponsiveContainer width="100%" height={260}>
              <ComposedChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis dataKey="date" tick={{ fill: 'var(--muted-foreground)', fontSize: 10 }} />
                <YAxis tick={{ fill: 'var(--muted-foreground)', fontSize: 10 }} domain={['auto', 'auto']} />
                <Tooltip
                  contentStyle={{ background: 'var(--card)', border: '1px solid var(--border)', color: 'var(--foreground)' }}
                />
                <Legend />
                <Line type="monotone" dataKey="close" stroke="var(--primary)" dot={false} strokeWidth={2} name="收盤" />
                {activeIndicators.includes('boll') && (
                  <>
                    <Line type="monotone" dataKey="bollUpper" stroke="#f59e0b" dot={false} strokeWidth={1} strokeDasharray="4 2" name="布林上軌" />
                    <Line type="monotone" dataKey="bollMiddle" stroke="#8b5cf6" dot={false} strokeWidth={1} strokeDasharray="4 2" name="布林中軌" />
                    <Line type="monotone" dataKey="bollLower" stroke="#f59e0b" dot={false} strokeWidth={1} strokeDasharray="4 2" name="布林下軌" />
                  </>
                )}
                <Bar dataKey="volume" fill="var(--secondary)" name="成交量" yAxisId={1} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>

          {/* MACD */}
          {activeIndicators.includes('macd') && (
            <div
              className="rounded-lg p-4"
              style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
            >
              <h3 className="text-sm font-medium mb-3" style={{ color: 'var(--muted-foreground)' }}>MACD</h3>
              <ResponsiveContainer width="100%" height={150}>
                <ComposedChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="date" tick={{ fill: 'var(--muted-foreground)', fontSize: 10 }} />
                  <YAxis tick={{ fill: 'var(--muted-foreground)', fontSize: 10 }} />
                  <Tooltip contentStyle={{ background: 'var(--card)', border: '1px solid var(--border)', color: 'var(--foreground)' }} />
                  <Bar dataKey="macdHist" fill="var(--primary)" name="柱狀" />
                  <Line type="monotone" dataKey="macd" stroke="#ef4444" dot={false} strokeWidth={1.5} name="MACD" />
                  <Line type="monotone" dataKey="macdSignal" stroke="#f59e0b" dot={false} strokeWidth={1.5} name="Signal" />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* KD */}
          {activeIndicators.includes('kd') && (
            <div
              className="rounded-lg p-4"
              style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
            >
              <h3 className="text-sm font-medium mb-3" style={{ color: 'var(--muted-foreground)' }}>KD 指標</h3>
              <ResponsiveContainer width="100%" height={150}>
                <ComposedChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="date" tick={{ fill: 'var(--muted-foreground)', fontSize: 10 }} />
                  <YAxis domain={[0, 100]} tick={{ fill: 'var(--muted-foreground)', fontSize: 10 }} />
                  <Tooltip contentStyle={{ background: 'var(--card)', border: '1px solid var(--border)', color: 'var(--foreground)' }} />
                  <Legend />
                  <Line type="monotone" dataKey="kdK" stroke="#3b82f6" dot={false} strokeWidth={1.5} name="K" />
                  <Line type="monotone" dataKey="kdD" stroke="#f59e0b" dot={false} strokeWidth={1.5} name="D" />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* RSI */}
          {activeIndicators.includes('rsi') && (
            <div
              className="rounded-lg p-4"
              style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
            >
              <h3 className="text-sm font-medium mb-3" style={{ color: 'var(--muted-foreground)' }}>RSI(14)</h3>
              <ResponsiveContainer width="100%" height={150}>
                <ComposedChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="date" tick={{ fill: 'var(--muted-foreground)', fontSize: 10 }} />
                  <YAxis domain={[0, 100]} tick={{ fill: 'var(--muted-foreground)', fontSize: 10 }} />
                  <Tooltip contentStyle={{ background: 'var(--card)', border: '1px solid var(--border)', color: 'var(--foreground)' }} />
                  <Line type="monotone" dataKey="rsi" stroke="#8b5cf6" dot={false} strokeWidth={1.5} name="RSI" />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      ) : (
        <div
          className="rounded-lg p-6 text-center"
          style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
        >
          <p style={{ color: 'var(--muted-foreground)' }}>查無 {stockCode} 的技術分析資料</p>
        </div>
      )}
    </div>
  )
}
