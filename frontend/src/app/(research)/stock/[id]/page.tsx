'use client'

import { use, useState, useRef, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import useSWR, { useSWRConfig } from 'swr'
import { useRefreshInterval } from '@/lib/hooks/useRefreshInterval'
import { fetchAPI } from '@/lib/api/client'
import { KpiCard } from '@/components/shared/KpiCard'
import { StockInput } from '@/components/shared/StockInput'
import { ScreenshotImportDialog } from '@/components/shared/ScreenshotImportDialog'
import { formatPrice, formatPercent, formatChange, getChangeColorVar } from '@/lib/utils/format'
import { ratingColor } from '@/lib/constants/chartColors'
import {
  getQuoteRefreshInterval,
  quoteStatusColor,
  quoteStatusLabel,
  quoteTimeLabel,
  type RealtimeQuote,
} from '@/lib/quotes/realtime'
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
  company_profile?: CompanyProfile
}

interface CompanyProfile {
  stock_id: string
  name?: string
  company_full_name?: string
  market?: string
  industry?: string
  business_scope?: string
  business_summary?: string
  product_lines?: string[]
  revenue_sources?: Array<{
    period?: string
    name: string
    amount_thousand_twd?: number
    ratio_pct?: number
  }>
  website?: string
  capital?: string
  chairman?: string
  general_manager?: string
  profile_sources?: Array<{ name: string; url?: string }>
  updated_at?: string
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
interface InstitutionChip {
  total_shares: number
  daily?: Array<{ date: string; shares: number }>
}

interface ChipResponse {
  stock_id: string
  外資?: InstitutionChip
  投信?: InstitutionChip
  自營商?: InstitutionChip
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

interface ScoreHistoryResponse {
  history: Array<{
    date: string
    total_score: number | null
    rating: string
    change: number | null
    rating_changed: boolean
  }>
  score_change: number | null
}

interface StockSummaryResponse {
  stance: string
  score: number | null
  rating: string
  summary: string
  key_points: string[]
  strengths: Array<{ component: string; label: string; score: number | null }>
  weaknesses: Array<{ component: string; label: string; score: number | null }>
}

const SCORE_COMPONENT_ORDER: ScoreComponentKey[] = ['value', 'growth', 'momentum', 'chip', 'quality', 'risk']

function formatScore(score: number | null | undefined): string {
  return score == null ? '—' : score.toFixed(1)
}

export default function StockDetailPage({ params }: StockDetailPageProps) {
  const refreshInterval = useRefreshInterval()
  const { id } = use(params)
  const { mutate } = useSWRConfig()
  const router = useRouter()
  const [tab, setTab] = useState<TabType>('chart')
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([])
  const [chatInput, setChatInput] = useState('')
  const [chatLoading, setChatLoading] = useState(false)
  const [importOpen, setImportOpen] = useState(false)
  const chatBottomRef = useRef<HTMLDivElement>(null)

  const { data: stock, isLoading: stockLoading, error: stockError } = useSWR<StockDetail>(
    `/stock/${id}`,
    fetchAPI
  )

  const { data: liveQuote, error: quoteError } = useSWR<RealtimeQuote>(
    `/quote/realtime/${id}`,
    fetchAPI,
    {
      refreshInterval: () => refreshInterval(getQuoteRefreshInterval()),
      dedupingInterval: 10_000,
      revalidateOnFocus: true,
    }
  )

  const { data: ohlcv, isLoading: ohlcvLoading, error: ohlcvError } = useSWR<OhlcvResponse>(
    tab === 'chart' ? `/stock/${id}/ohlcv?days=120` : null,
    fetchAPI
  )

  const { data: technical, error: technicalError } = useSWR<TechnicalResponse>(
    tab === 'technical' ? `/stock/${id}/technical` : null,
    fetchAPI
  )

  const { data: chip, error: chipError } = useSWR<ChipResponse>(
    tab === 'chip' ? `/stock/${id}/chip` : null,
    fetchAPI
  )

  const { data: scorecard, error: scorecardError } = useSWR<ScorecardResponse>(
    `/stock/${id}/scorecard`,
    fetchAPI
  )

  const { data: companyProfile, error: companyProfileError } = useSWR<CompanyProfile>(
    `/stock/${id}/profile`,
    fetchAPI
  )

  const { data: scoreHistory, error: scoreHistoryError } = useSWR<ScoreHistoryResponse>(
    `/stock/${id}/score-history?days=20`,
    fetchAPI
  )

  const { data: stockSummary, error: stockSummaryError } = useSWR<StockSummaryResponse>(
    `/ai/stock-summary/${id}`,
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

  const retryStockRequests = () => Promise.all([
    mutate(`/stock/${id}`),
    mutate(`/quote/realtime/${id}`),
    mutate(`/stock/${id}/ohlcv?days=120`),
    mutate(`/stock/${id}/scorecard`),
    mutate(`/stock/${id}/profile`),
    mutate(`/stock/${id}/score-history?days=20`),
    mutate(`/ai/stock-summary/${id}`),
  ])

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

  if (stockError && !stock) {
    return (
      <div>
        <div className="mb-6 flex items-center gap-4">
          <h1 className="text-2xl font-bold shrink-0" style={{ color: 'var(--foreground)' }}>個股分析 — {id}</h1>
          <StockInput
            value={id}
            onChange={(newId) => { if (newId !== id) router.push(`/stock/${newId}`) }}
            placeholder="切換股票：輸入代號或名稱"
            className="flex-1 max-w-sm"
          />
        </div>
        <div className="rounded-lg p-8 text-center" style={{ background: 'var(--card)', border: '1px solid var(--border)' }}>
          <p className="font-medium" style={{ color: 'var(--destructive)' }}>個股資料載入失敗</p>
          <p className="mt-2 text-sm" style={{ color: 'var(--muted-foreground)' }}>無法取得 {id} 的最新資料，請稍後重試或切換其他股票。</p>
          <button
            type="button"
            onClick={() => mutate(`/stock/${id}`)}
            className="mt-4 h-9 rounded-md px-4 text-sm font-medium"
            style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}
          >
            重新載入
          </button>
        </div>
      </div>
    )
  }

  const hasPartialError = Boolean(
    quoteError || ohlcvError || scorecardError || companyProfileError ||
    scoreHistoryError || stockSummaryError
  )
  const displayPrice = liveQuote?.price ?? stock?.latest_price
  const displayChangePct = liveQuote?.change_pct ?? stock?.change_pct

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
          <button
            type="button"
            onClick={() => setImportOpen(true)}
            aria-label="截圖辨識個股"
            className="shrink-0 rounded-lg px-3 py-2 text-sm font-medium transition-opacity hover:opacity-80"
            style={{
              background: 'var(--secondary)',
              color: 'var(--foreground)',
              border: '1px solid var(--border)',
            }}
          >
            📷 截圖辨識
          </button>
        </div>
        <div className="flex items-center gap-2 text-sm mt-1" style={{ color: 'var(--muted-foreground)' }}>
          <span>個股詳細分析</span>
          {liveQuote ? (
            <span style={{ color: quoteStatusColor(liveQuote) }}>
              {quoteStatusLabel(liveQuote)} · {quoteTimeLabel(liveQuote)}
            </span>
          ) : stock ? (
            <span>收盤 · FinLab · {stock.date ?? '—'}</span>
          ) : null}
        </div>
      </div>

      {hasPartialError && (
        <div className="mb-4 flex items-center justify-between rounded-lg p-3" role="alert" style={{ background: 'var(--card)', border: '1px solid var(--destructive)' }}>
          <p className="text-sm" style={{ color: 'var(--destructive)' }}>部分分析資料載入失敗，目前顯示可用資料。</p>
          <button type="button" onClick={retryStockRequests} className="text-sm font-medium" style={{ color: 'var(--primary)' }}>重新載入</button>
        </div>
      )}

      {/* KPI 列 */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
        <KpiCard
          title="現價"
          value={displayPrice != null ? formatPrice(displayPrice) : '—'}
          changeLabel={displayChangePct != null ? formatPercent(displayChangePct) : undefined}
          isLoading={stockLoading && !liveQuote}
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
          value={stock?.pe_ratio != null ? formatPrice(stock.pe_ratio) : '—'}
          isLoading={stockLoading}
          accentColor="var(--flow-dealer)"
        />
        <KpiCard
          title="股價淨值比 PB"
          value={stock?.pb_ratio != null ? formatPrice(stock.pb_ratio) : '—'}
          isLoading={stockLoading}
          accentColor="var(--flow-trust)"
        />
        <KpiCard
          title="殖利率"
          value={stock?.dividend_yield != null ? `${formatPrice(stock.dividend_yield)}%` : '—'}
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
                <p className="text-2xl font-bold tabular-nums" style={{ color: ratingColor(scorecard.rating) }}>
                  {formatScore(scorecard.total_score)}
                </p>
              </div>
              <div
                className="h-12 w-12 rounded-md flex items-center justify-center text-lg font-bold"
                style={{
                  background: 'var(--secondary)',
                  color: ratingColor(scorecard.rating),
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
                      style={{ width: `${width}%`, background: ratingColor(scorecard.rating) }}
                    />
                  </div>
                </div>
              )
            })}
          </div>

          <div className="flex flex-wrap gap-x-4 gap-y-1 mt-3 text-xs" style={{ color: 'var(--muted-foreground)' }}>
            <span>資料日期：{scorecard.date ?? '—'}</span>
            <span>可用構面：{scorecard.available_components}/6</span>
            {scoreHistory?.score_change != null && (
              <span style={{ color: getChangeColorVar(scoreHistory.score_change) }}>
                近 20 日評分：{formatChange(scoreHistory.score_change)}
              </span>
            )}
            {scorecard.key_metrics.revenue_mom != null && (
              <span>營收月增率：{formatPercent(scorecard.key_metrics.revenue_mom)}</span>
            )}
          </div>

          {scoreHistory?.history?.length ? (
            <div className="mt-4 grid grid-cols-5 md:grid-cols-10 gap-1">
              {scoreHistory.history.slice(-10).map((point) => (
                <div key={point.date} className="rounded-md p-2 text-center" style={{ background: 'var(--secondary)' }}>
                  <p className="text-[10px]" style={{ color: 'var(--muted-foreground)' }}>{point.date.slice(5)}</p>
                  <p className="text-xs font-semibold tabular-nums" style={{ color: ratingColor(point.rating) }}>
                    {formatScore(point.total_score)}
                  </p>
                </div>
              ))}
            </div>
          ) : null}
        </div>
      )}

      {/* AI 摘要 */}
      {stockSummary && (
        <div
          className="rounded-lg p-4 mb-6"
          style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
        >
          <div className="flex items-start justify-between gap-3 mb-3">
            <div>
              <h2 className="text-base font-semibold" style={{ color: 'var(--foreground)' }}>AI 個股摘要</h2>
              <p className="text-xs mt-0.5" style={{ color: 'var(--muted-foreground)' }}>
                由量化分數、基本面與構面強弱自動產生
              </p>
            </div>
            <span className="px-2 py-1 rounded text-xs font-medium" style={{ background: 'var(--secondary)', color: ratingColor(stockSummary.rating) }}>
              {stockSummary.stance}
            </span>
          </div>
          <p className="text-sm leading-relaxed mb-3" style={{ color: 'var(--foreground)' }}>{stockSummary.summary}</p>
          <div className="grid md:grid-cols-2 gap-3">
            {stockSummary.key_points.slice(0, 4).map((point) => (
              <div key={point} className="rounded-md p-3 text-sm" style={{ background: 'var(--secondary)', color: 'var(--foreground)' }}>
                {point}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 公司營運概況 */}
      {(companyProfile ?? stock?.company_profile) && (
        <div
          className="rounded-lg p-4 mb-6"
          style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
        >
          {(() => {
            const profile = companyProfile ?? stock?.company_profile
            if (!profile) return null
            return (
              <>
                <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-3 mb-4">
                  <div>
                    <h2 className="text-base font-semibold" style={{ color: 'var(--foreground)' }}>公司營運概況</h2>
                    <p className="text-xs mt-0.5" style={{ color: 'var(--muted-foreground)' }}>
                      {profile.company_full_name || profile.name || id}
                      {profile.market ? ` / ${profile.market}` : ''}
                      {profile.industry ? ` / ${profile.industry}` : ''}
                    </p>
                  </div>
                  {profile.updated_at && (
                    <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>更新 {profile.updated_at}</span>
                  )}
                </div>

                {profile.business_summary && (
                  <p className="text-sm leading-relaxed mb-4" style={{ color: 'var(--foreground)' }}>
                    {profile.business_summary}
                  </p>
                )}

                <div className="grid md:grid-cols-2 gap-3">
                  <div className="rounded-md p-3" style={{ background: 'var(--secondary)' }}>
                    <p className="text-xs mb-2" style={{ color: 'var(--muted-foreground)' }}>主要產品線</p>
                    {profile.product_lines?.length ? (
                      <div className="flex flex-wrap gap-2">
                        {profile.product_lines.map((product) => (
                          <span key={product} className="px-2 py-1 rounded text-xs" style={{ background: 'var(--card)', color: 'var(--foreground)', border: '1px solid var(--border)' }}>
                            {product}
                          </span>
                        ))}
                      </div>
                    ) : (
                      <p className="text-sm" style={{ color: 'var(--muted-foreground)' }}>尚無產品線資料</p>
                    )}
                  </div>

                  <div className="rounded-md p-3" style={{ background: 'var(--secondary)' }}>
                    <p className="text-xs mb-2" style={{ color: 'var(--muted-foreground)' }}>營收來源</p>
                    {profile.revenue_sources?.length ? (
                      <div className="space-y-2">
                        {profile.revenue_sources.map((source) => (
                          <div key={`${source.period}-${source.name}`}>
                            <div className="flex justify-between text-xs mb-1">
                              <span style={{ color: 'var(--foreground)' }}>{source.name}</span>
                              <span style={{ color: 'var(--muted-foreground)' }}>
                                {source.ratio_pct != null ? `${formatPrice(source.ratio_pct)}%` : source.period ?? ''}
                              </span>
                            </div>
                            {source.ratio_pct != null && (
                              <div className="h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--border)' }}>
                                <div className="h-full rounded-full" style={{ width: `${Math.min(100, source.ratio_pct)}%`, background: 'var(--primary)' }} />
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-sm" style={{ color: 'var(--muted-foreground)' }}>尚無營收結構資料</p>
                    )}
                  </div>
                </div>

                <div className="flex flex-wrap gap-x-4 gap-y-1 mt-3 text-xs" style={{ color: 'var(--muted-foreground)' }}>
                  {profile.business_scope && <span>業務範圍：{profile.business_scope}</span>}
                  {profile.capital && <span>資本額：{profile.capital}</span>}
                  {profile.website && <span>網站：{profile.website}</span>}
                </div>
              </>
            )
          })()}
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
                {formatPercent(stock.revenue_yoy)}
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
              {ohlcvError ? (
                <div className="h-64 flex items-center justify-center" style={{ color: 'var(--destructive)' }}>
                  走勢資料載入失敗，請重試
                </div>
              ) : ohlcvLoading ? (
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
              {technicalError ? (
                <p style={{ color: 'var(--destructive)' }}>技術指標載入失敗，請切換頁籤後重試。</p>
              ) : technical ? (
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
                          {formatPrice(technical.sma.sma5)}
                        </p>
                      </div>
                    )}
                    {technical.sma?.sma20 != null && (
                      <div className="rounded-md p-3" style={{ background: 'var(--secondary)' }}>
                        <p className="text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>MA20</p>
                        <p className="font-semibold tabular-nums" style={{ color: 'var(--foreground)' }}>
                          {formatPrice(technical.sma.sma20)}
                        </p>
                      </div>
                    )}
                    {technical.sma?.sma60 != null && (
                      <div className="rounded-md p-3" style={{ background: 'var(--secondary)' }}>
                        <p className="text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>MA60</p>
                        <p className="font-semibold tabular-nums" style={{ color: 'var(--foreground)' }}>
                          {formatPrice(technical.sma.sma60)}
                        </p>
                      </div>
                    )}
                    {/* RSI */}
                    {technical.rsi_14 != null && (
                      <div className="rounded-md p-3" style={{ background: 'var(--secondary)' }}>
                        <p className="text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>RSI(14)</p>
                        <p className="font-semibold tabular-nums" style={{ color: 'var(--foreground)' }}>
                          {formatPrice(technical.rsi_14)}
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
                          {formatPrice(technical.macd.macd)}
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
                          {formatPrice(technical.macd.signal)}
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
                          {formatPrice(technical.macd.histogram)}
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
              {chipError ? (
                <p style={{ color: 'var(--destructive)' }}>籌碼資料載入失敗，請切換頁籤後重試。</p>
              ) : chip ? (
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
                        { label: '外資', total: chip['外資']?.total_shares },
                        { label: '投信', total: chip['投信']?.total_shares },
                        { label: '自營商', total: chip['自營商']?.total_shares },
                      ] as { label: string; total?: number }[]).filter(r => r.total != null).map(({ label, total }) => {
                        const lots = Math.round(total! / 1000)
                        return (
                        <tr key={label} style={{ borderBottom: '1px solid var(--border)' }}>
                          <td className="py-2 px-3" style={{ color: 'var(--foreground)' }}>{label}</td>
                          <td
                            className="py-2 px-3 font-semibold tabular-nums"
                            style={{ color: getChangeColorVar(lots) }}
                          >
                            {lots > 0 ? '+' : ''}{lots.toLocaleString()}
                          </td>
                        </tr>
                      )})}
                    </tbody>
                  </table>
                  {chip.foreign_holding_pct != null && (
                    <div className="rounded-md p-3 mt-2" style={{ background: 'var(--secondary)' }}>
                      <p className="text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>外資持股比例</p>
                      <p className="font-semibold" style={{ color: 'var(--foreground)' }}>
                        {formatPrice(chip.foreign_holding_pct)}%
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
                      { label: '本益比 (PE)', value: stock.pe_ratio != null ? formatPrice(stock.pe_ratio) : '—' },
                      { label: '股價淨值比 (PB)', value: stock.pb_ratio != null ? formatPrice(stock.pb_ratio) : '—' },
                      { label: '殖利率', value: stock.dividend_yield != null ? `${formatPrice(stock.dividend_yield)}%` : '—' },
                      { label: '營收年增率', value: stock.revenue_yoy != null ? formatPercent(stock.revenue_yoy) : '—' },
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
          role="log"
          aria-live="polite"
          aria-label="AI 對話"
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
            aria-label="輸入問題"
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
            aria-label="送出問題"
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

      {/* 截圖辨識個股：codes 模式，點 chip 即跳轉該股分析 */}
      <ScreenshotImportDialog
        open={importOpen}
        onClose={() => setImportOpen(false)}
        mode="codes"
        title="📷 截圖辨識個股"
        onPickOne={(stockId) => {
          setImportOpen(false)
          router.push(`/stock/${stockId}`)
        }}
      />
    </div>
  )
}
