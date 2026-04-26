'use client'

import { use, useState, useRef, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import useSWR from 'swr'
import { fetchAPI } from '@/lib/api/client'
import { KpiCard } from '@/components/shared/KpiCard'
import { StockInput } from '@/components/shared/StockInput'
import { formatPrice, formatPercent, getChangeColorVar } from '@/lib/utils/format'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts'

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

interface StockDetailPageProps {
  params: Promise<{ id: string }>
}

type TabType = 'chart' | 'technical' | 'chip' | 'basic'
type ScoreComponentKey = 'value' | 'growth' | 'momentum' | 'chip' | 'quality' | 'risk'

// GET /stock/:id
interface StockDetail {
  stock_id: string
  name: string
  industry?: string
  latest_price: number
  change_pct: number
  date?: string
  pe_ratio?: number
  pb_ratio?: number
  dividend_yield?: number
  revenue_yoy?: number
  price_history?: Array<{ date: string; price: number }>
}

// GET /stock/:id/ohlcv?days=120
interface OhlcvResponse {
  stock_id: string
  days: number
  data: Array<{
    date: string
    open: number
    high: number
    low: number
    close: number
    volume: number
  }>
}

// GET /stock/:id/technical
interface TechnicalResponse {
  stock_id: string
  name: string
  rsi_14?: number
  macd?: {
    macd: number
    signal: number
    histogram: number
  }
  sma?: {
    sma5?: number
    sma20?: number
    sma60?: number
  }
  trend?: string
}

// GET /stock/:id/chip
interface InstitutionalLatest {
  latest?: number
  [key: string]: unknown
}

interface ChipResponse {
  stock_id: string
  name: string
  foreign_buy_sell?: InstitutionalLatest
  trust_buy_sell?: InstitutionalLatest
  dealer_buy_sell?: InstitutionalLatest
  foreign_holding_pct?: number
}

interface ScorecardResponse {
  stock_id: string
  name?: string
  industry?: string
  date?: string
  total_score: number | null
  rating: string
  component_scores: Record<ScoreComponentKey, number | null>
  component_labels: Record<ScoreComponentKey, string>
  key_metrics: {
    latest_price?: number | null
    pe_ratio?: number | null
    pb_ratio?: number | null
    dividend_yield?: number | null
    revenue_yoy?: number | null
    revenue_mom?: number | null
  }
  available_components: number
}

const SCORE_COMPONENT_ORDER: ScoreComponentKey[] = ['value', 'growth', 'momentum', 'chip', 'quality', 'risk']

function getRatingColor(rating: string): string {
  if (rating === 'A') return '#22c55e'
  if (rating === 'B') return '#84cc16'
  if (rating === 'C') return '#f59e0b'
  if (rating === 'D') return '#f97316'
  if (rating === 'F') return '#ef4444'
  return 'var(--muted-foreground)'
}

function formatScore(score: number | null | undefined): string {
  return score == null ? '—' : score.toFixed(1)
}

export default function StockDetailPage({ params }: StockDetailPageProps) {
  const { id } = use(params)
  const router = useRouter()
  const [tab, setTab] = useState<TabType>('chart')
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([])
  const [chatInput, setChatInput] = useState('')
  const [chatLoading, setChatLoading] = useState(false)
  const chatBottomRef = useRef<HTMLDivElement>(null)

  const { data: stock, isLoading: stockLoading } = useSWR<StockDetail>(
    `/stock/${id}`,
    fetchAPI
  )

  const { data: ohlcv, isLoading: ohlcvLoading } = useSWR<OhlcvResponse>(
    tab === 'chart' ? `/stock/${id}/ohlcv?days=120` : null,
    fetchAPI
  )

  const { data: technical } = useSWR<TechnicalResponse>(
    tab === 'technical' ? `/stock/${id}/technical` : null,
    fetchAPI
  )

  const { data: chip } = useSWR<ChipResponse>(
    tab === 'chip' ? `/stock/${id}/chip` : null,
    fetchAPI
  )

  const { data: scorecard } = useSWR<ScorecardResponse>(
    `/stock/${id}/scorecard`,
    fetchAPI
  )

  const tabs: { key: TabType; label: string }[] = [
    { key: 'chart', label: '走勢圖' },
    { key: 'technical', label: '技術分析' },
    { key: 'chip', label: '籌碼' },
    { key: 'basic', label: '基本資料' },
  ]

  // OHLCV 資料，取 close 欄位畫折線
  const chartData = ohlcv?.data ?? []

  // Auto-scroll chat to bottom whenever messages update
  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [chatMessages, chatLoading])

  async function sendChat() {
    const question = chatInput.trim()
    if (!question || chatLoading) return

    const userMsg: ChatMessage = { role: 'user', content: question }
    const nextMessages = [...chatMessages, userMsg]
    setChatMessages(nextMessages)
    setChatInput('')
    setChatLoading(true)

    try {
      const history = nextMessages.slice(0, -1).map((m) => ({ role: m.role, content: m.content }))
      const res = await fetchAPI<{ reply: string; stock_id: string; name: string }>(
        '/ai/stock-chat',
        { method: 'POST', body: JSON.stringify({ stock_id: id, question, history }) },
        60000
      )
      setChatMessages([...nextMessages, { role: 'assistant', content: res.reply }])
    } catch {
      setChatMessages([...nextMessages, { role: 'assistant', content: '⚠️ 發生錯誤，請稍後再試。' }])
    } finally {
      setChatLoading(false)
    }
  }

  return (
    <div>
      <div className="mb-6">
        <div className="flex items-center gap-4 mb-3">
          <h1 className="text-2xl font-bold shrink-0" style={{ color: 'var(--foreground)' }}>
            {stock ? `${stock.stock_id} ${stock.name}` : `個股分析 — ${id}`}
          </h1>
          <StockInput
            value={id}
            onChange={(newId) => { if (newId !== id) router.push(`/stock/${newId}`) }}
            placeholder="切換股票：輸入代號或名稱"
            className="flex-1 max-w-sm"
          />
        </div>
        <p className="text-sm mt-1" style={{ color: 'var(--muted-foreground)' }}>個股詳細分析</p>
      </div>

      {/* KPI 列 */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
        <KpiCard
          title="現價"
          value={stock ? formatPrice(stock.latest_price) : '—'}
          changeLabel={stock ? formatPercent(stock.change_pct) : undefined}
          isLoading={stockLoading}
          accentColor="var(--primary)"
        />
        <KpiCard
          title="產業別"
          value={stock?.industry ?? '—'}
          isLoading={stockLoading}
          accentColor="var(--muted-foreground)"
        />
        <KpiCard
          title="本益比 PE"
          value={stock?.pe_ratio != null ? stock.pe_ratio.toFixed(2) : '—'}
          isLoading={stockLoading}
          accentColor="#8b5cf6"
        />
        <KpiCard
          title="股價淨值比 PB"
          value={stock?.pb_ratio != null ? stock.pb_ratio.toFixed(2) : '—'}
          isLoading={stockLoading}
          accentColor="#f59e0b"
        />
        <KpiCard
          title="殖利率"
          value={stock?.dividend_yield != null ? `${stock.dividend_yield.toFixed(2)}%` : '—'}
          isLoading={stockLoading}
          accentColor="var(--stock-down)"
        />
      </div>

      {/* 量化評分卡 */}
      {scorecard && (
        <div
          className="rounded-lg p-4 mb-6"
          style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
        >
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-4">
            <div>
              <h2 className="text-base font-semibold" style={{ color: 'var(--foreground)' }}>量化評分卡</h2>
              <p className="text-xs mt-0.5" style={{ color: 'var(--muted-foreground)' }}>
                價值、成長、動能、籌碼、品質、風險六構面綜合評估
              </p>
            </div>
            <div className="flex items-center gap-3">
              <div className="text-right">
                <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>總分</p>
                <p className="text-2xl font-bold tabular-nums" style={{ color: getRatingColor(scorecard.rating) }}>
                  {formatScore(scorecard.total_score)}
                </p>
              </div>
              <div
                className="h-12 w-12 rounded-md flex items-center justify-center text-lg font-bold"
                style={{
                  background: 'var(--secondary)',
                  color: getRatingColor(scorecard.rating),
                  border: '1px solid var(--border)',
                }}
                aria-label={`量化評級 ${scorecard.rating}`}
              >
                {scorecard.rating}
              </div>
            </div>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-6 gap-2">
            {SCORE_COMPONENT_ORDER.map((key) => {
              const score = scorecard.component_scores[key]
              const label = scorecard.component_labels[key] ?? key
              const width = Math.max(0, Math.min(100, score ?? 0))
              return (
                <div key={key} className="rounded-md p-3" style={{ background: 'var(--secondary)' }}>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>{label}</span>
                    <span className="text-xs font-semibold tabular-nums" style={{ color: 'var(--foreground)' }}>
                      {formatScore(score)}
                    </span>
                  </div>
                  <div
                    className="h-1.5 rounded-full overflow-hidden"
                    style={{ background: 'var(--border)' }}
                    aria-label={`${label}分數 ${formatScore(score)}`}
                  >
                    <div
                      className="h-full rounded-full"
                      style={{ width: `${width}%`, background: getRatingColor(scorecard.rating) }}
                    />
                  </div>
                </div>
              )
            })}
          </div>

          <div className="flex flex-wrap gap-x-4 gap-y-1 mt-3 text-xs" style={{ color: 'var(--muted-foreground)' }}>
            <span>資料日期：{scorecard.date ?? '—'}</span>
            <span>可用構面：{scorecard.available_components}/6</span>
            {scorecard.key_metrics.revenue_mom != null && (
              <span>營收月增率：{scorecard.key_metrics.revenue_mom.toFixed(2)}%</span>
            )}
          </div>
        </div>
      )}

      {/* 今日行情摘要 */}
      {stock && (
        <div
          className="rounded-lg p-4 mb-6 flex flex-wrap gap-6"
          style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
        >
          <div>
            <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>漲跌幅</span>
            <p
              className="font-semibold"
              style={{ color: getChangeColorVar(stock.change_pct) }}
            >
              {formatPercent(stock.change_pct)}
            </p>
          </div>
          {stock.revenue_yoy != null && (
            <div>
              <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>營收年增率</span>
              <p
                className="font-semibold"
                style={{ color: getChangeColorVar(stock.revenue_yoy) }}
              >
                {stock.revenue_yoy.toFixed(2)}%
              </p>
            </div>
          )}
          {stock.date && (
            <div>
              <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>資料日期</span>
              <p className="font-semibold" style={{ color: 'var(--foreground)' }}>{stock.date}</p>
            </div>
          )}
        </div>
      )}

      {/* Tabs */}
      <div
        className="rounded-lg overflow-hidden"
        style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
      >
        <div className="flex border-b" style={{ borderColor: 'var(--border)' }}>
          {tabs.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className="px-5 py-3 text-sm font-medium transition-colors"
              style={{
                color: tab === t.key ? 'var(--primary)' : 'var(--muted-foreground)',
                borderBottom: tab === t.key ? '2px solid var(--primary)' : '2px solid transparent',
              }}
            >
              {t.label}
            </button>
          ))}
        </div>

        <div className="p-4">
          {/* 走勢圖 Tab：使用 /stock/{id}/ohlcv?days=120 */}
          {tab === 'chart' && (
            <div>
              <h3 className="text-sm font-medium mb-4" style={{ color: 'var(--muted-foreground)' }}>
                近 120 日收盤走勢
              </h3>
              {ohlcvLoading ? (
                <div className="h-64 flex items-center justify-center" style={{ color: 'var(--muted-foreground)' }}>
                  載入走勢資料中...
                </div>
              ) : chartData.length > 0 ? (
                <ResponsiveContainer width="100%" height={300}>
                  <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                    <XAxis
                      dataKey="date"
                      tick={{ fill: 'var(--muted-foreground)', fontSize: 11 }}
                      tickFormatter={(v: string) => v.slice(5)}
                    />
                    <YAxis
                      tick={{ fill: 'var(--muted-foreground)', fontSize: 11 }}
                      domain={['auto', 'auto']}
                      width={60}
                    />
                    <Tooltip
                      contentStyle={{
                        background: 'var(--card)',
                        border: '1px solid var(--border)',
                        color: 'var(--foreground)',
                      }}
                      formatter={(value) => [
                        typeof value === 'number' ? formatPrice(value) : String(value ?? '—'),
                        '收盤價' as string,
                      ]}
                    />
                    <Line
                      type="monotone"
                      dataKey="close"
                      stroke="var(--primary)"
                      dot={false}
                      strokeWidth={2}
                      name="收盤價"
                    />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-64 flex items-center justify-center" style={{ color: 'var(--muted-foreground)' }}>
                  暫無走勢資料
                </div>
              )}
            </div>
          )}

          {/* 技術分析 Tab：使用 /stock/{id}/technical */}
          {tab === 'technical' && (
            <div className="space-y-4">
              <h3 className="text-sm font-medium" style={{ color: 'var(--muted-foreground)' }}>技術指標</h3>
              {technical ? (
                <>
                  {/* 趨勢判斷 */}
                  {technical.trend && (
                    <div
                      className="rounded-md p-3 flex items-center gap-2"
                      style={{ background: 'var(--secondary)' }}
                    >
                      <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>趨勢判斷</span>
                      <span className="font-semibold" style={{ color: 'var(--foreground)' }}>
                        {technical.trend}
                      </span>
                    </div>
                  )}

                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    {/* SMA 均線 */}
                    {technical.sma?.sma5 != null && (
                      <div className="rounded-md p-3" style={{ background: 'var(--secondary)' }}>
                        <p className="text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>MA5</p>
                        <p className="font-semibold tabular-nums" style={{ color: 'var(--foreground)' }}>
                          {technical.sma.sma5.toFixed(2)}
                        </p>
                      </div>
                    )}
                    {technical.sma?.sma20 != null && (
                      <div className="rounded-md p-3" style={{ background: 'var(--secondary)' }}>
                        <p className="text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>MA20</p>
                        <p className="font-semibold tabular-nums" style={{ color: 'var(--foreground)' }}>
                          {technical.sma.sma20.toFixed(2)}
                        </p>
                      </div>
                    )}
                    {technical.sma?.sma60 != null && (
                      <div className="rounded-md p-3" style={{ background: 'var(--secondary)' }}>
                        <p className="text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>MA60</p>
                        <p className="font-semibold tabular-nums" style={{ color: 'var(--foreground)' }}>
                          {technical.sma.sma60.toFixed(2)}
                        </p>
                      </div>
                    )}
                    {/* RSI */}
                    {technical.rsi_14 != null && (
                      <div className="rounded-md p-3" style={{ background: 'var(--secondary)' }}>
                        <p className="text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>RSI(14)</p>
                        <p className="font-semibold tabular-nums" style={{ color: 'var(--foreground)' }}>
                          {technical.rsi_14.toFixed(2)}
                        </p>
                      </div>
                    )}
                    {/* MACD */}
                    {technical.macd?.macd != null && (
                      <div className="rounded-md p-3" style={{ background: 'var(--secondary)' }}>
                        <p className="text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>MACD</p>
                        <p
                          className="font-semibold tabular-nums"
                          style={{ color: getChangeColorVar(technical.macd.macd) }}
                        >
                          {technical.macd.macd.toFixed(2)}
                        </p>
                      </div>
                    )}
                    {technical.macd?.signal != null && (
                      <div className="rounded-md p-3" style={{ background: 'var(--secondary)' }}>
                        <p className="text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>Signal</p>
                        <p
                          className="font-semibold tabular-nums"
                          style={{ color: getChangeColorVar(technical.macd.signal) }}
                        >
                          {technical.macd.signal.toFixed(2)}
                        </p>
                      </div>
                    )}
                    {technical.macd?.histogram != null && (
                      <div className="rounded-md p-3" style={{ background: 'var(--secondary)' }}>
                        <p className="text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>柱狀值</p>
                        <p
                          className="font-semibold tabular-nums"
                          style={{ color: getChangeColorVar(technical.macd.histogram) }}
                        >
                          {technical.macd.histogram.toFixed(2)}
                        </p>
                      </div>
                    )}
                  </div>
                </>
              ) : (
                <p style={{ color: 'var(--muted-foreground)' }}>載入技術指標中...</p>
              )}
            </div>
          )}

          {/* 籌碼 Tab：使用 /stock/{id}/chip */}
          {tab === 'chip' && (
            <div className="space-y-4">
              <h3 className="text-sm font-medium" style={{ color: 'var(--muted-foreground)' }}>三大法人買賣超</h3>
              {chip ? (
                <>
                  <table className="w-full text-sm">
                    <thead>
                      <tr style={{ borderBottom: '1px solid var(--border)' }}>
                        {['法人', '最新買賣超 (張)'].map((h) => (
                          <th key={h} className="text-left py-2 px-3" style={{ color: 'var(--muted-foreground)' }}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {([
                        { label: '外資', latest: chip.foreign_buy_sell?.latest },
                        { label: '投信', latest: chip.trust_buy_sell?.latest },
                        { label: '自營商', latest: chip.dealer_buy_sell?.latest },
                      ] as { label: string; latest?: number }[]).filter(r => r.latest != null).map(({ label, latest }) => (
                        <tr key={label} style={{ borderBottom: '1px solid var(--border)' }}>
                          <td className="py-2 px-3" style={{ color: 'var(--foreground)' }}>{label}</td>
                          <td
                            className="py-2 px-3 font-semibold tabular-nums"
                            style={{ color: getChangeColorVar(latest!) }}
                          >
                            {latest! > 0 ? '+' : ''}{latest!.toLocaleString()}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {chip.foreign_holding_pct != null && (
                    <div className="rounded-md p-3 mt-2" style={{ background: 'var(--secondary)' }}>
                      <p className="text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>外資持股比例</p>
                      <p className="font-semibold" style={{ color: 'var(--foreground)' }}>
                        {chip.foreign_holding_pct.toFixed(2)}%
                      </p>
                    </div>
                  )}
                </>
              ) : (
                <p style={{ color: 'var(--muted-foreground)' }}>載入籌碼資料中...</p>
              )}
            </div>
          )}

          {/* 基本資料 Tab */}
          {tab === 'basic' && (
            <div>
              <h3 className="text-sm font-medium mb-4" style={{ color: 'var(--muted-foreground)' }}>基本資料</h3>
              {stock ? (
                <table className="w-full text-sm">
                  <tbody>
                    {[
                      { label: '股票代號', value: stock.stock_id },
                      { label: '公司名稱', value: stock.name },
                      { label: '產業別', value: stock.industry ?? '—' },
                      { label: '現價', value: formatPrice(stock.latest_price) },
                      { label: '漲跌幅', value: formatPercent(stock.change_pct) },
                      { label: '本益比 (PE)', value: stock.pe_ratio?.toFixed(2) ?? '—' },
                      { label: '股價淨值比 (PB)', value: stock.pb_ratio?.toFixed(2) ?? '—' },
                      { label: '殖利率', value: stock.dividend_yield != null ? `${stock.dividend_yield.toFixed(2)}%` : '—' },
                      { label: '營收年增率', value: stock.revenue_yoy != null ? `${stock.revenue_yoy.toFixed(2)}%` : '—' },
                      { label: '資料日期', value: stock.date ?? '—' },
                    ].map(({ label, value }) => (
                      <tr key={label} style={{ borderBottom: '1px solid var(--border)' }}>
                        <td className="py-2 px-3 w-36" style={{ color: 'var(--muted-foreground)' }}>{label}</td>
                        <td className="py-2 px-3" style={{ color: 'var(--foreground)' }}>{value}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p style={{ color: 'var(--muted-foreground)' }}>載入基本資料中...</p>
              )}
            </div>
          )}
        </div>
      </div>

      {/* AI 個股問答 */}
      <div
        className="rounded-lg overflow-hidden mt-6"
        style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
      >
        {/* Header */}
        <div
          className="px-4 py-3 border-b"
          style={{ borderColor: 'var(--border)' }}
        >
          <h2 className="text-sm font-semibold" style={{ color: 'var(--foreground)' }}>
            🤖 AI 個股問答
          </h2>
          <p className="text-xs mt-0.5" style={{ color: 'var(--muted-foreground)' }}>
            針對 {stock ? `${stock.stock_id} ${stock.name}` : id} 提問，AI 將根據現有資料回答
          </p>
        </div>

        {/* Message history */}
        <div
          className="flex flex-col gap-3 p-4 overflow-y-auto"
          style={{ height: '320px' }}
        >
          {chatMessages.length === 0 && !chatLoading && (
            <div
              className="flex-1 flex items-center justify-center text-sm"
              style={{ color: 'var(--muted-foreground)' }}
            >
              輸入問題開始對話，例如「這檔適合進場嗎？」
            </div>
          )}

          {chatMessages.map((msg, idx) => (
            <div
              key={idx}
              className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className="max-w-[80%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap"
                style={
                  msg.role === 'user'
                    ? {
                        background: 'var(--primary)',
                        color: 'var(--primary-foreground)',
                        borderBottomRightRadius: '4px',
                      }
                    : {
                        background: 'var(--secondary)',
                        color: 'var(--foreground)',
                        borderBottomLeftRadius: '4px',
                      }
                }
              >
                {msg.content}
              </div>
            </div>
          ))}

          {chatLoading && (
            <div className="flex justify-start">
              <div
                className="rounded-2xl px-4 py-2.5 text-sm"
                style={{
                  background: 'var(--secondary)',
                  color: 'var(--muted-foreground)',
                  borderBottomLeftRadius: '4px',
                }}
              >
                <span className="inline-flex gap-1">
                  <span className="animate-bounce" style={{ animationDelay: '0ms' }}>●</span>
                  <span className="animate-bounce" style={{ animationDelay: '150ms' }}>●</span>
                  <span className="animate-bounce" style={{ animationDelay: '300ms' }}>●</span>
                </span>
              </div>
            </div>
          )}

          <div ref={chatBottomRef} />
        </div>

        {/* Input bar */}
        <div
          className="flex gap-2 px-4 py-3 border-t"
          style={{ borderColor: 'var(--border)' }}
        >
          <input
            type="text"
            value={chatInput}
            onChange={(e) => setChatInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendChat() } }}
            placeholder="輸入問題…"
            disabled={chatLoading}
            className="flex-1 rounded-lg px-3 py-2 text-sm outline-none"
            style={{
              background: 'var(--secondary)',
              color: 'var(--foreground)',
              border: '1px solid var(--border)',
            }}
          />
          <button
            onClick={sendChat}
            disabled={chatLoading || !chatInput.trim()}
            className="rounded-lg px-4 py-2 text-sm font-medium transition-opacity disabled:opacity-40"
            style={{
              background: 'var(--primary)',
              color: 'var(--primary-foreground)',
            }}
          >
            送出
          </button>
        </div>
      </div>
    </div>
  )
}
