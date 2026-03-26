'use client'

import { useState } from 'react'
import useSWR from 'swr'
import { fetchAPI } from '@/lib/api/client'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
  CartesianGrid,
} from 'recharts'

// ─── Types ───────────────────────────────────────────────────────────────────

interface XGBoostStock {
  stock_id: string
  name: string
  predicted_return: number
  confidence: number
  factors: Record<string, number>
}

interface XGBoostResponse {
  stocks: XGBoostStock[]
  feature_importance: Record<string, number>
}

interface PredictedPrice {
  day: number
  price: number
}

interface LSTMResponse {
  stock_id: string
  name: string
  direction: 'up' | 'down' | 'sideways'
  confidence: number
  predicted_prices: PredictedPrice[]
  trend_strength: number
}

interface ClaudeResponse {
  stock_id: string
  name: string
  summary: string
  recommendation: 'buy' | 'hold' | 'watch' | 'sell'
  risk_level: 'low' | 'medium' | 'high'
  key_factors: string[]
}

// Quant types (preserved from original)
interface ValueStock {
  stock_id: string
  price: number
  pe_ratio: number
  pb_ratio: number
  dividend_yield: number
  name: string
}
interface GrowthStock {
  stock_id: string
  price: number
  revenue_yoy: number
  revenue_mom: number
  name: string
}
interface MomentumStock {
  stock_id: string
  price: number
  volume_ratio: number
  rsi: number
  breakout_high: number
  name: string
}
interface StrategyGroup<T> {
  total: number
  stocks: T[]
}
interface AiPickResponse {
  date: string
  strategies: {
    value: StrategyGroup<ValueStock>
    growth: StrategyGroup<GrowthStock>
    momentum: StrategyGroup<MomentumStock>
  }
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

type MainTab = 'xgboost' | 'lstm' | 'claude' | 'quant'
type QuantTab = 'value' | 'growth' | 'momentum'

const QUANT_TAB_LABELS: Record<QuantTab, string> = {
  value: '價值選股',
  growth: '成長選股',
  momentum: '動能選股',
}

const RECOMMENDATION_CONFIG: Record<
  ClaudeResponse['recommendation'],
  { label: string; bg: string; color: string }
> = {
  buy: { label: '買入', bg: '#ef444422', color: '#ef4444' },
  hold: { label: '持有', bg: '#3b82f622', color: '#3b82f6' },
  watch: { label: '觀望', bg: '#64748b22', color: '#94a3b8' },
  sell: { label: '賣出', bg: '#22c55e22', color: '#22c55e' },
}

const RISK_CONFIG: Record<
  ClaudeResponse['risk_level'],
  { label: string; bg: string; color: string }
> = {
  low: { label: '低風險', bg: '#22c55e22', color: '#22c55e' },
  medium: { label: '中風險', bg: '#f59e0b22', color: '#f59e0b' },
  high: { label: '高風險', bg: '#ef444422', color: '#ef4444' },
}

const DIRECTION_CONFIG = {
  up: { label: '上漲', symbol: '▲', color: '#ef4444' },
  down: { label: '下跌', symbol: '▼', color: '#22c55e' },
  sideways: { label: '盤整', symbol: '─', color: '#94a3b8' },
}

// ─── Shared sub-components ───────────────────────────────────────────────────

function Card({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return (
    <div
      className={`rounded-lg ${className}`}
      style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
    >
      {children}
    </div>
  )
}

function ErrorCard({ message }: { message: string }) {
  return (
    <Card className="p-8 text-center">
      <p className="text-sm" style={{ color: 'var(--destructive)' }}>
        {message}
      </p>
    </Card>
  )
}

function LoadingCard() {
  return (
    <Card className="p-8 text-center">
      <p className="text-sm" style={{ color: 'var(--muted-foreground)' }}>
        載入中...
      </p>
    </Card>
  )
}

function StockInput({
  value,
  onChange,
  onSubmit,
  loading,
}: {
  value: string
  onChange: (v: string) => void
  onSubmit: () => void
  loading: boolean
}) {
  return (
    <div className="flex gap-2 mb-4">
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value.toUpperCase())}
        onKeyDown={(e) => e.key === 'Enter' && onSubmit()}
        placeholder="輸入股票代號，例：2330"
        maxLength={6}
        className="h-9 rounded-md border px-3 text-sm w-48"
        style={{
          background: 'var(--background)',
          border: '1px solid var(--border)',
          color: 'var(--foreground)',
        }}
      />
      <button
        onClick={onSubmit}
        disabled={loading || !value.trim()}
        className="h-9 px-4 rounded-md text-sm font-medium disabled:opacity-60"
        style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}
      >
        {loading ? '查詢中...' : '查詢'}
      </button>
    </div>
  )
}

function Badge({
  label,
  bg,
  color,
}: {
  label: string
  bg: string
  color: string
}) {
  return (
    <span
      className="inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold"
      style={{ background: bg, color }}
    >
      {label}
    </span>
  )
}

// ─── XGBoost Tab ─────────────────────────────────────────────────────────────

function XGBoostTab() {
  const { data, isLoading, error } = useSWR<XGBoostResponse>(
    '/ai/xgboost?top_n=20',
    fetchAPI
  )

  if (error) {
    return (
      <ErrorCard message="XGBoost 模型尚未安裝或服務不可用。請確認後端已配置 scikit-learn 及相關依賴。" />
    )
  }
  if (isLoading) return <LoadingCard />
  if (!data) return null

  const importanceData = Object.entries(data.feature_importance)
    .sort(([, a], [, b]) => b - a)
    .slice(0, 10)
    .map(([name, value]) => ({ name, value: parseFloat((value * 100).toFixed(1)) }))

  return (
    <div className="space-y-4">
      {/* Ranking table */}
      <Card className="overflow-hidden">
        <div
          className="px-4 py-3 border-b"
          style={{ borderColor: 'var(--border)' }}
        >
          <h3 className="text-sm font-medium" style={{ color: 'var(--foreground)' }}>
            XGBoost 選股排行 — 共 {data.stocks.length} 支
          </h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr style={{ background: 'var(--secondary)' }}>
                {['排名', '代號', '名稱', '預測報酬率', '信心度'].map((h) => (
                  <th
                    key={h}
                    className="text-left py-2 px-4"
                    style={{ color: 'var(--muted-foreground)' }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.stocks.map((row, i) => (
                <tr key={row.stock_id} style={{ borderBottom: '1px solid var(--border)' }}>
                  <td
                    className="py-2 px-4 tabular-nums"
                    style={{ color: 'var(--muted-foreground)' }}
                  >
                    {i + 1}
                  </td>
                  <td
                    className="py-2 px-4 font-medium tabular-nums"
                    style={{ color: 'var(--primary)' }}
                  >
                    {row.stock_id}
                  </td>
                  <td className="py-2 px-4" style={{ color: 'var(--foreground)' }}>
                    {row.name}
                  </td>
                  <td
                    className="py-2 px-4 tabular-nums font-semibold"
                    style={{
                      color:
                        row.predicted_return >= 0
                          ? 'var(--stock-up)'
                          : 'var(--stock-down)',
                    }}
                  >
                    {row.predicted_return >= 0 ? '+' : ''}
                    {(row.predicted_return * 100).toFixed(2)}%
                  </td>
                  <td className="py-2 px-4 tabular-nums" style={{ color: 'var(--foreground)' }}>
                    <div className="flex items-center gap-2">
                      <div
                        className="h-1.5 rounded-full flex-1 max-w-20"
                        style={{ background: 'var(--border)' }}
                      >
                        <div
                          className="h-1.5 rounded-full"
                          style={{
                            width: `${(row.confidence * 100).toFixed(0)}%`,
                            background: 'var(--primary)',
                          }}
                        />
                      </div>
                      <span className="text-xs tabular-nums">
                        {(row.confidence * 100).toFixed(1)}%
                      </span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Feature Importance Chart */}
      {importanceData.length > 0 && (
        <Card className="p-4">
          <h3
            className="text-sm font-medium mb-4"
            style={{ color: 'var(--foreground)' }}
          >
            特徵重要性 (Feature Importance)
          </h3>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart
              data={importanceData}
              layout="vertical"
              margin={{ top: 0, right: 20, left: 20, bottom: 0 }}
            >
              <XAxis
                type="number"
                tickFormatter={(v) => `${v}%`}
                tick={{ fill: '#94a3b8', fontSize: 11 }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                type="category"
                dataKey="name"
                width={100}
                tick={{ fill: '#94a3b8', fontSize: 11 }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip
                contentStyle={{
                  background: 'var(--card)',
                  border: '1px solid var(--border)',
                  borderRadius: 6,
                  color: 'var(--foreground)',
                  fontSize: 12,
                }}
                formatter={(v) => [`${v}%`, '重要性']}
              />
              <Bar dataKey="value" fill="#3b82f6" radius={[0, 3, 3, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      )}
    </div>
  )
}

// ─── LSTM Tab ─────────────────────────────────────────────────────────────────

function LSTMTab() {
  const [inputValue, setInputValue] = useState('')
  const [stockId, setStockId] = useState<string | null>(null)

  const { data, isLoading, error } = useSWR<LSTMResponse>(
    stockId ? `/ai/lstm/${stockId}` : null,
    fetchAPI
  )

  const handleSubmit = () => {
    const trimmed = inputValue.trim()
    if (trimmed) setStockId(trimmed)
  }

  const dirConfig = data ? DIRECTION_CONFIG[data.direction] : null

  return (
    <div>
      <StockInput
        value={inputValue}
        onChange={setInputValue}
        onSubmit={handleSubmit}
        loading={isLoading}
      />

      {!stockId && (
        <Card className="p-8 text-center">
          <p className="text-sm" style={{ color: 'var(--muted-foreground)' }}>
            輸入股票代號以查詢 LSTM 趨勢預測
          </p>
        </Card>
      )}

      {stockId && error && (
        <ErrorCard message="LSTM 模型尚未安裝或服務不可用。請確認後端已配置 TensorFlow/PyTorch 及相關依賴。" />
      )}

      {stockId && isLoading && <LoadingCard />}

      {data && dirConfig && (
        <div className="space-y-4">
          {/* Direction card */}
          <Card className="p-6">
            <div className="flex items-center justify-between mb-2">
              <div>
                <span
                  className="text-sm font-medium"
                  style={{ color: 'var(--muted-foreground)' }}
                >
                  {data.stock_id}
                </span>
                <span className="ml-2 text-sm" style={{ color: 'var(--foreground)' }}>
                  {data.name}
                </span>
              </div>
              <span
                className="text-xs px-2 py-0.5 rounded-full"
                style={{
                  background: 'var(--secondary)',
                  color: 'var(--muted-foreground)',
                }}
              >
                趨勢強度 {(data.trend_strength * 100).toFixed(1)}%
              </span>
            </div>

            <div className="flex items-center gap-4 mt-4">
              <span
                className="text-6xl font-bold tabular-nums"
                style={{ color: dirConfig.color }}
              >
                {dirConfig.symbol}
              </span>
              <div>
                <p
                  className="text-3xl font-bold"
                  style={{ color: dirConfig.color }}
                >
                  {dirConfig.label}
                </p>
                <p className="text-sm mt-1" style={{ color: 'var(--muted-foreground)' }}>
                  信心度：
                  <span
                    className="font-semibold tabular-nums"
                    style={{ color: 'var(--foreground)' }}
                  >
                    {(data.confidence * 100).toFixed(1)}%
                  </span>
                </p>
              </div>
            </div>
          </Card>

          {/* Price chart */}
          {data.predicted_prices.length > 0 && (
            <Card className="p-4">
              <h3
                className="text-sm font-medium mb-4"
                style={{ color: 'var(--foreground)' }}
              >
                未來 {data.predicted_prices.length} 天預測價格
              </h3>
              <ResponsiveContainer width="100%" height={220}>
                <LineChart
                  data={data.predicted_prices.map((p) => ({
                    day: `第${p.day}天`,
                    price: p.price,
                  }))}
                  margin={{ top: 4, right: 16, left: 0, bottom: 0 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis
                    dataKey="day"
                    tick={{ fill: '#94a3b8', fontSize: 11 }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    tick={{ fill: '#94a3b8', fontSize: 11 }}
                    axisLine={false}
                    tickLine={false}
                    width={60}
                    tickFormatter={(v) => v.toFixed(0)}
                  />
                  <Tooltip
                    contentStyle={{
                      background: 'var(--card)',
                      border: '1px solid var(--border)',
                      borderRadius: 6,
                      color: 'var(--foreground)',
                      fontSize: 12,
                    }}
                    formatter={(v) => [typeof v === 'number' ? v.toFixed(2) : v, '預測價格']}
                  />
                  <Line
                    type="monotone"
                    dataKey="price"
                    stroke={dirConfig.color}
                    strokeWidth={2}
                    dot={{ fill: dirConfig.color, r: 4 }}
                    activeDot={{ r: 5 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </Card>
          )}
        </div>
      )}
    </div>
  )
}

// ─── Claude Tab ───────────────────────────────────────────────────────────────

function ClaudeTab() {
  const [inputValue, setInputValue] = useState('')
  const [stockId, setStockId] = useState<string | null>(null)

  const { data, isLoading, error } = useSWR<ClaudeResponse>(
    stockId ? `/ai/claude/${stockId}` : null,
    fetchAPI
  )

  const handleSubmit = () => {
    const trimmed = inputValue.trim()
    if (trimmed) setStockId(trimmed)
  }

  return (
    <div>
      <StockInput
        value={inputValue}
        onChange={setInputValue}
        onSubmit={handleSubmit}
        loading={isLoading}
      />

      {!stockId && (
        <Card className="p-8 text-center">
          <p className="text-sm" style={{ color: 'var(--muted-foreground)' }}>
            輸入股票代號以查詢 Claude AI 分析報告
          </p>
        </Card>
      )}

      {stockId && error && (
        <ErrorCard message="Claude AI 分析服務不可用。請確認後端已配置 Anthropic API 金鑰及相關依賴。" />
      )}

      {stockId && isLoading && <LoadingCard />}

      {data && (
        <Card className="p-6">
          {/* Header */}
          <div className="flex items-start justify-between mb-4">
            <div>
              <span
                className="text-sm font-medium tabular-nums"
                style={{ color: 'var(--primary)' }}
              >
                {data.stock_id}
              </span>
              <span className="ml-2 text-base font-semibold" style={{ color: 'var(--foreground)' }}>
                {data.name}
              </span>
            </div>
            <div className="flex items-center gap-2">
              {RECOMMENDATION_CONFIG[data.recommendation] && (
                <Badge {...RECOMMENDATION_CONFIG[data.recommendation]} />
              )}
              {RISK_CONFIG[data.risk_level] && (
                <Badge {...RISK_CONFIG[data.risk_level]} />
              )}
            </div>
          </div>

          {/* Summary */}
          <div className="mb-4">
            <p
              className="text-xs font-medium mb-1"
              style={{ color: 'var(--muted-foreground)' }}
            >
              分析摘要
            </p>
            <p className="text-sm leading-relaxed" style={{ color: 'var(--foreground)' }}>
              {data.summary}
            </p>
          </div>

          {/* Key factors */}
          {data.key_factors.length > 0 && (
            <div>
              <p
                className="text-xs font-medium mb-2"
                style={{ color: 'var(--muted-foreground)' }}
              >
                關鍵因素
              </p>
              <ul className="space-y-1.5">
                {data.key_factors.map((factor, i) => (
                  <li key={i} className="flex items-start gap-2">
                    <span
                      className="mt-0.5 text-xs font-bold"
                      style={{ color: 'var(--primary)' }}
                    >
                      {i + 1}.
                    </span>
                    <span className="text-sm" style={{ color: 'var(--foreground)' }}>
                      {factor}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </Card>
      )}
    </div>
  )
}

// ─── Quant Tab (preserved) ────────────────────────────────────────────────────

function QuantTab() {
  const [activeQuantTab, setActiveQuantTab] = useState<QuantTab>('value')

  const { data, isLoading, error } = useSWR<AiPickResponse>(
    '/strategy/ai-pick',
    fetchAPI
  )

  if (error) {
    return <ErrorCard message="量化選股資料載入失敗" />
  }
  if (isLoading) return <LoadingCard />
  if (!data) return null

  return (
    <div>
      {/* Sub-tabs */}
      <div className="flex gap-2 mb-4">
        {(Object.keys(QUANT_TAB_LABELS) as QuantTab[]).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveQuantTab(tab)}
            className="px-5 py-2 rounded-md text-sm font-medium transition-colors"
            style={{
              background:
                activeQuantTab === tab ? 'var(--primary)' : 'var(--secondary)',
              color:
                activeQuantTab === tab
                  ? 'var(--primary-foreground)'
                  : 'var(--foreground)',
            }}
          >
            {QUANT_TAB_LABELS[tab]}
            <span
              className="ml-2 text-xs px-1.5 py-0.5 rounded-full"
              style={{
                background:
                  activeQuantTab === tab
                    ? 'rgba(255,255,255,0.2)'
                    : 'var(--border)',
                color:
                  activeQuantTab === tab
                    ? 'var(--primary-foreground)'
                    : 'var(--muted-foreground)',
              }}
            >
              {data.strategies[tab].total}
            </span>
          </button>
        ))}
      </div>

      <Card className="overflow-hidden">
        <div
          className="px-4 py-3 border-b flex justify-between items-center"
          style={{ borderColor: 'var(--border)' }}
        >
          <h3 className="text-sm font-medium" style={{ color: 'var(--foreground)' }}>
            {QUANT_TAB_LABELS[activeQuantTab]} — 共{' '}
            {data.strategies[activeQuantTab].total} 支
          </h3>
          <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
            {data.date}
          </span>
        </div>
        <div className="overflow-x-auto">
          {activeQuantTab === 'value' && (
            <table className="w-full text-sm">
              <thead>
                <tr style={{ background: 'var(--secondary)' }}>
                  {['排名', '代號', '名稱', '現價', 'PE', 'PB', '殖利率%'].map(
                    (h) => (
                      <th
                        key={h}
                        className="text-left py-2 px-4"
                        style={{ color: 'var(--muted-foreground)' }}
                      >
                        {h}
                      </th>
                    )
                  )}
                </tr>
              </thead>
              <tbody>
                {data.strategies.value.stocks.map((row, i) => (
                  <tr
                    key={row.stock_id}
                    style={{ borderBottom: '1px solid var(--border)' }}
                  >
                    <td
                      className="py-2 px-4 tabular-nums"
                      style={{ color: 'var(--muted-foreground)' }}
                    >
                      {i + 1}
                    </td>
                    <td
                      className="py-2 px-4 font-medium"
                      style={{ color: 'var(--primary)' }}
                    >
                      {row.stock_id}
                    </td>
                    <td className="py-2 px-4" style={{ color: 'var(--foreground)' }}>
                      {row.name}
                    </td>
                    <td
                      className="py-2 px-4 tabular-nums"
                      style={{ color: 'var(--foreground)' }}
                    >
                      {row.price.toFixed(2)}
                    </td>
                    <td
                      className="py-2 px-4 tabular-nums"
                      style={{ color: 'var(--foreground)' }}
                    >
                      {row.pe_ratio.toFixed(1)}
                    </td>
                    <td
                      className="py-2 px-4 tabular-nums"
                      style={{ color: 'var(--foreground)' }}
                    >
                      {row.pb_ratio.toFixed(2)}
                    </td>
                    <td
                      className="py-2 px-4 tabular-nums font-semibold"
                      style={{ color: 'var(--primary)' }}
                    >
                      {row.dividend_yield.toFixed(2)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          {activeQuantTab === 'growth' && (
            <table className="w-full text-sm">
              <thead>
                <tr style={{ background: 'var(--secondary)' }}>
                  {['排名', '代號', '名稱', '現價', '年增率%', '月增率%'].map(
                    (h) => (
                      <th
                        key={h}
                        className="text-left py-2 px-4"
                        style={{ color: 'var(--muted-foreground)' }}
                      >
                        {h}
                      </th>
                    )
                  )}
                </tr>
              </thead>
              <tbody>
                {data.strategies.growth.stocks.map((row, i) => (
                  <tr
                    key={row.stock_id}
                    style={{ borderBottom: '1px solid var(--border)' }}
                  >
                    <td
                      className="py-2 px-4 tabular-nums"
                      style={{ color: 'var(--muted-foreground)' }}
                    >
                      {i + 1}
                    </td>
                    <td
                      className="py-2 px-4 font-medium"
                      style={{ color: 'var(--primary)' }}
                    >
                      {row.stock_id}
                    </td>
                    <td className="py-2 px-4" style={{ color: 'var(--foreground)' }}>
                      {row.name}
                    </td>
                    <td
                      className="py-2 px-4 tabular-nums"
                      style={{ color: 'var(--foreground)' }}
                    >
                      {row.price.toFixed(2)}
                    </td>
                    <td
                      className="py-2 px-4 tabular-nums font-semibold"
                      style={{ color: 'var(--stock-up)' }}
                    >
                      +{row.revenue_yoy.toFixed(2)}%
                    </td>
                    <td
                      className="py-2 px-4 tabular-nums font-semibold"
                      style={{
                        color:
                          row.revenue_mom >= 0
                            ? 'var(--stock-up)'
                            : 'var(--stock-down)',
                      }}
                    >
                      {row.revenue_mom >= 0 ? '+' : ''}
                      {row.revenue_mom.toFixed(2)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          {activeQuantTab === 'momentum' && (
            <table className="w-full text-sm">
              <thead>
                <tr style={{ background: 'var(--secondary)' }}>
                  {[
                    '排名',
                    '代號',
                    '名稱',
                    '現價',
                    '量比',
                    'RSI',
                    '突破高點',
                  ].map((h) => (
                    <th
                      key={h}
                      className="text-left py-2 px-4"
                      style={{ color: 'var(--muted-foreground)' }}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.strategies.momentum.stocks.map((row, i) => (
                  <tr
                    key={row.stock_id}
                    style={{ borderBottom: '1px solid var(--border)' }}
                  >
                    <td
                      className="py-2 px-4 tabular-nums"
                      style={{ color: 'var(--muted-foreground)' }}
                    >
                      {i + 1}
                    </td>
                    <td
                      className="py-2 px-4 font-medium"
                      style={{ color: 'var(--primary)' }}
                    >
                      {row.stock_id}
                    </td>
                    <td className="py-2 px-4" style={{ color: 'var(--foreground)' }}>
                      {row.name}
                    </td>
                    <td
                      className="py-2 px-4 tabular-nums"
                      style={{ color: 'var(--foreground)' }}
                    >
                      {row.price.toFixed(2)}
                    </td>
                    <td
                      className="py-2 px-4 tabular-nums font-semibold"
                      style={{ color: 'var(--primary)' }}
                    >
                      {row.volume_ratio.toFixed(2)}x
                    </td>
                    <td
                      className="py-2 px-4 tabular-nums"
                      style={{
                        color:
                          row.rsi > 70
                            ? 'var(--stock-down)'
                            : row.rsi < 30
                            ? 'var(--stock-up)'
                            : 'var(--foreground)',
                      }}
                    >
                      {row.rsi.toFixed(1)}
                    </td>
                    <td
                      className="py-2 px-4 tabular-nums"
                      style={{ color: 'var(--muted-foreground)' }}
                    >
                      {row.breakout_high.toFixed(2)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </Card>
    </div>
  )
}

// ─── Main Page ────────────────────────────────────────────────────────────────

const MAIN_TABS: { value: MainTab; label: string }[] = [
  { value: 'xgboost', label: 'XGBoost 選股' },
  { value: 'lstm', label: 'LSTM 趨勢' },
  { value: 'claude', label: 'Claude 分析' },
  { value: 'quant', label: '量化篩選' },
]

export default function AiPickPage() {
  const [activeTab, setActiveTab] = useState<MainTab>('xgboost')

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold" style={{ color: 'var(--foreground)' }}>
          AI 智慧選股
        </h1>
        <p className="text-sm mt-1" style={{ color: 'var(--muted-foreground)' }}>
          整合多種 AI 模型的智慧選股與分析平台
        </p>
      </div>

      {/* Main Tab Bar */}
      <div
        className="flex gap-1 mb-5 p-1 rounded-lg w-fit"
        style={{ background: 'var(--secondary)' }}
      >
        {MAIN_TABS.map((tab) => (
          <button
            key={tab.value}
            onClick={() => setActiveTab(tab.value)}
            className="px-4 py-2 rounded-md text-sm font-medium transition-colors"
            style={{
              background:
                activeTab === tab.value
                  ? 'var(--card)'
                  : 'transparent',
              color:
                activeTab === tab.value
                  ? 'var(--foreground)'
                  : 'var(--muted-foreground)',
              boxShadow:
                activeTab === tab.value
                  ? '0 1px 3px rgba(0,0,0,0.3)'
                  : 'none',
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {activeTab === 'xgboost' && <XGBoostTab />}
      {activeTab === 'lstm' && <LSTMTab />}
      {activeTab === 'claude' && <ClaudeTab />}
      {activeTab === 'quant' && <QuantTab />}
    </div>
  )
}
