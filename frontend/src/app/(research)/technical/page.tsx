'use client'

import { useState } from 'react'
import type { ReactNode } from 'react'
import useSWR from 'swr'
import { fetchAPI } from '@/lib/api/client'
import { StockInput } from '@/components/shared/StockInput'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { Info } from 'lucide-react'
import {
  ComposedChart, Line, Bar, XAxis, YAxis, CartesianGrid, Tooltip as ChartTooltip, ResponsiveContainer, Legend
} from 'recharts'

interface TechnicalChartItem {
  date: string
  close: number
  sma5?: number
  sma20?: number
  sma60?: number
  rsi14?: number
  macd?: number
  macd_signal?: number
  macd_hist?: number
  bb_upper?: number
  bb_mid?: number
  bb_lower?: number
  kdj_k?: number
  kdj_d?: number
  kdj_j?: number
}

interface TechnicalChartResponse {
  stock_id: string
  days: number
  data: TechnicalChartItem[]
}

type Indicator = 'macd' | 'kd' | 'rsi' | 'boll'

const PERIODS: { label: string; value: string; days: number }[] = [
  { label: '1 個月', value: '1m', days: 30 },
  { label: '3 個月', value: '3m', days: 90 },
  { label: '6 個月', value: '6m', days: 180 },
  { label: '1 年', value: '1y', days: 365 },
]

const INDICATORS: { key: Indicator; label: string; title: string; description: string; usage: string }[] = [
  {
    key: 'macd',
    label: 'MACD',
    title: 'MACD 趨勢動能',
    description: '用快慢均線的差距判斷趨勢動能與轉折。MACD 線上穿 Signal 線常被視為偏多訊號，下穿則偏弱。',
    usage: '柱狀體擴大代表動能增強；接近零軸時通常表示趨勢正在轉換。',
  },
  {
    key: 'kd',
    label: 'KD',
    title: 'KD 隨機指標',
    description: '衡量股價在近期高低區間中的相對位置，常用來觀察短線超買、超賣與轉折。',
    usage: 'K、D 高於 80 偏熱，低於 20 偏冷；K 線上穿 D 線偏多，下穿偏弱。',
  },
  {
    key: 'rsi',
    label: 'RSI',
    title: 'RSI 相對強弱',
    description: '比較近期上漲與下跌力道，判斷買盤或賣壓是否過熱。',
    usage: 'RSI 高於 70 常代表超買，低於 30 常代表超賣；背離可用來留意趨勢衰退。',
  },
  {
    key: 'boll',
    label: '布林通道',
    title: '布林通道 波動區間',
    description: '以均線加減標準差形成上、中、下軌，觀察價格是否偏離正常波動範圍。',
    usage: '靠近上軌代表價格偏強或偏熱，靠近下軌代表偏弱或可能反彈；通道收斂常表示波動將放大。',
  },
]

const indicatorMap = Object.fromEntries(INDICATORS.map((indicator) => [indicator.key, indicator])) as Record<Indicator, (typeof INDICATORS)[number]>

function IndicatorHelp({ indicator }: { indicator: Indicator }) {
  const item = indicatorMap[indicator]

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          aria-label={`${item.label} 指標說明`}
          className="inline-flex h-5 w-5 items-center justify-center rounded-full transition-colors hover:bg-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          style={{ color: 'var(--muted-foreground)' }}
        >
          <Info className="h-3.5 w-3.5" aria-hidden="true" />
        </button>
      </TooltipTrigger>
      <TooltipContent side="top" align="start" className="max-w-72 space-y-1.5 px-3 py-2 leading-relaxed">
        <p className="font-medium">{item.title}</p>
        <p className="text-xs opacity-90">{item.description}</p>
        <p className="text-xs opacity-75">{item.usage}</p>
      </TooltipContent>
    </Tooltip>
  )
}

function IndicatorHeading({ indicator, children }: { indicator: Indicator; children: ReactNode }) {
  return (
    <div className="mb-3 flex items-center gap-1.5">
      <h3 className="text-sm font-medium" style={{ color: 'var(--muted-foreground)' }}>{children}</h3>
      <IndicatorHelp indicator={indicator} />
    </div>
  )
}

export default function TechnicalPage() {
  const [stockCode, setStockCode] = useState('')
  const [period, setPeriod] = useState('3m')
  const [activeIndicators, setActiveIndicators] = useState<Indicator[]>(['macd'])

  const selectedPeriod = PERIODS.find(p => p.value === period) ?? PERIODS[1]

  const { data: response, isLoading, error } = useSWR<TechnicalChartResponse>(
    stockCode
      ? `/stock/${stockCode}/technical-chart?days=${selectedPeriod.days}`
      : null,
    fetchAPI
  )

  const chartData = response?.data ?? []

  const toggleIndicator = (ind: Indicator) => {
    setActiveIndicators(prev =>
      prev.includes(ind) ? prev.filter(i => i !== ind) : [...prev, ind]
    )
  }

  return (
    <TooltipProvider delayDuration={150}>
      <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold" style={{ color: 'var(--foreground)' }}>技術分析</h1>
        <p className="text-sm mt-1" style={{ color: 'var(--muted-foreground)' }}>收盤價走勢與技術指標</p>
      </div>

      {/* 控制列 */}
      <div
        className="rounded-lg p-4 mb-6 flex flex-wrap gap-3 items-end"
        style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
      >
        <div className="flex-1 min-w-48">
          <StockInput
            value={stockCode}
            onChange={setStockCode}
            label="股票代號"
            placeholder="例：2330 或 台積電"
          />
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
                <IndicatorHelp indicator={ind.key} />
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
      ) : chartData.length > 0 ? (
        <div className="space-y-4">
          {/* 收盤價 + 均線 */}
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
                <ChartTooltip
                  contentStyle={{ background: 'var(--card)', border: '1px solid var(--border)', color: 'var(--foreground)' }}
                />
                <Legend />
                <Line type="monotone" dataKey="close" stroke="var(--primary)" dot={false} strokeWidth={2} name="收盤" />
                <Line type="monotone" dataKey="sma5" stroke="#3b82f6" dot={false} strokeWidth={1} strokeDasharray="4 2" name="MA5" />
                <Line type="monotone" dataKey="sma20" stroke="#f59e0b" dot={false} strokeWidth={1} strokeDasharray="4 2" name="MA20" />
                <Line type="monotone" dataKey="sma60" stroke="#10b981" dot={false} strokeWidth={1} strokeDasharray="4 2" name="MA60" />
                {activeIndicators.includes('boll') && (
                  <>
                    <Line type="monotone" dataKey="bb_upper" stroke="#f59e0b" dot={false} strokeWidth={1} strokeDasharray="4 2" name="布林上軌" />
                    <Line type="monotone" dataKey="bb_mid" stroke="#8b5cf6" dot={false} strokeWidth={1} strokeDasharray="4 2" name="布林中軌" />
                    <Line type="monotone" dataKey="bb_lower" stroke="#f59e0b" dot={false} strokeWidth={1} strokeDasharray="4 2" name="布林下軌" />
                  </>
                )}
              </ComposedChart>
            </ResponsiveContainer>
          </div>

          {/* MACD */}
          {activeIndicators.includes('macd') && (
            <div
              className="rounded-lg p-4"
              style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
            >
              <IndicatorHeading indicator="macd">MACD</IndicatorHeading>
              <ResponsiveContainer width="100%" height={150}>
                <ComposedChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="date" tick={{ fill: 'var(--muted-foreground)', fontSize: 10 }} />
                  <YAxis tick={{ fill: 'var(--muted-foreground)', fontSize: 10 }} />
                  <ChartTooltip contentStyle={{ background: 'var(--card)', border: '1px solid var(--border)', color: 'var(--foreground)' }} />
                  <Bar dataKey="macd_hist" fill="var(--primary)" name="柱狀" />
                  <Line type="monotone" dataKey="macd" stroke="#ef4444" dot={false} strokeWidth={1.5} name="MACD" />
                  <Line type="monotone" dataKey="macd_signal" stroke="#f59e0b" dot={false} strokeWidth={1.5} name="Signal" />
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
              <IndicatorHeading indicator="kd">KD 指標</IndicatorHeading>
              <ResponsiveContainer width="100%" height={150}>
                <ComposedChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="date" tick={{ fill: 'var(--muted-foreground)', fontSize: 10 }} />
                  <YAxis domain={[0, 100]} tick={{ fill: 'var(--muted-foreground)', fontSize: 10 }} />
                  <ChartTooltip contentStyle={{ background: 'var(--card)', border: '1px solid var(--border)', color: 'var(--foreground)' }} />
                  <Legend />
                  <Line type="monotone" dataKey="kdj_k" stroke="#3b82f6" dot={false} strokeWidth={1.5} name="K" />
                  <Line type="monotone" dataKey="kdj_d" stroke="#f59e0b" dot={false} strokeWidth={1.5} name="D" />
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
              <IndicatorHeading indicator="rsi">RSI(14)</IndicatorHeading>
              <ResponsiveContainer width="100%" height={150}>
                <ComposedChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="date" tick={{ fill: 'var(--muted-foreground)', fontSize: 10 }} />
                  <YAxis domain={[0, 100]} tick={{ fill: 'var(--muted-foreground)', fontSize: 10 }} />
                  <ChartTooltip contentStyle={{ background: 'var(--card)', border: '1px solid var(--border)', color: 'var(--foreground)' }} />
                  <Line type="monotone" dataKey="rsi14" stroke="#8b5cf6" dot={false} strokeWidth={1.5} name="RSI" />
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
    </TooltipProvider>
  )
}
