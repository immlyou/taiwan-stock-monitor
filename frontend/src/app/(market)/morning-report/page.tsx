'use client'

import { useState } from 'react'
import useSWR from 'swr'
import { fetchAPI } from '@/lib/api/client'
import { EmptyState } from '@/components/shared/EmptyState'
import { Skeleton } from '@/components/ui/skeleton'
import { formatDate, getChangeColorVar, formatPercent } from '@/lib/utils/format'

interface MorningReport {
  date: string
  summary: string
  keyPoints: string[]
  marketOutlook: string
}

interface NewsItem {
  id: string
  title: string
  source: string
  publishedAt: string
  url: string
  category: string
}

interface NewsApiResponse {
  total: number
  news: NewsItem[]
}

interface HotStock {
  code: string
  name: string
  mentionCount: number
  sentiment: 'positive' | 'negative' | 'neutral'
  changePercent: number
}

interface HotStockRaw {
  stock_id: string
  name: string
  total_score?: number
  news_score?: number
  sentiment?: 'positive' | 'negative' | 'neutral'
  change_pct?: number
  volume_ratio?: number
}

interface HotStocksApiResponse {
  total: number
  hot_stocks: HotStockRaw[]
}

interface AiSentimentNewsInput {
  title: string
  summary: string
  link: string
  source: string
}

interface AiSentimentResult {
  title: string
  link: string
  source: string
  sentiment: 'positive' | 'negative' | 'neutral'
  score: number
  impact: string
  related_stocks: string[]
}

interface AiSentimentResponse {
  results: AiSentimentResult[]
}

function useMorningReport() {
  const { data, error, isLoading } = useSWR<MorningReport>(
    '/morning-report',
    (path: string) => fetchAPI<MorningReport>(path),
    { refreshInterval: 300000, revalidateOnFocus: false }
  )
  return { report: data, isLoading, isError: !!error }
}

function useLatestNews() {
  const { data, error, isLoading } = useSWR<NewsApiResponse>(
    '/news/latest',
    (path: string) => fetchAPI<NewsApiResponse>(path),
    { refreshInterval: 60000 }
  )
  return { news: data?.news ?? [], isLoading, isError: !!error }
}

function useHotStocks() {
  const { data, isLoading } = useSWR<HotStocksApiResponse>(
    '/social/hot-stocks',
    (path: string) => fetchAPI<HotStocksApiResponse>(path),
    { refreshInterval: 120000 }
  )
  const hotStocks: HotStock[] = (data?.hot_stocks ?? []).map((s) => ({
    code: s.stock_id,
    name: s.name,
    mentionCount: Math.round((s.news_score ?? s.total_score ?? 0) * 10),
    sentiment: s.sentiment ?? 'neutral',
    changePercent: s.change_pct ?? 0,
  }))
  return { hotStocks, isLoading }
}

function SentimentBadge({ sentiment }: { sentiment: HotStock['sentiment'] }) {
  const map = {
    positive: { label: '偏多', color: 'var(--stock-up)' },
    negative: { label: '偏空', color: 'var(--stock-down)' },
    neutral: { label: '中性', color: 'var(--stock-flat)' },
  }
  const { label, color } = map[sentiment]
  return (
    <span
      className="text-xs px-1.5 py-0.5 rounded font-medium"
      style={{ color, border: `1px solid ${color}`, background: `${color}18` }}
    >
      {label}
    </span>
  )
}

export default function MorningReportPage() {
  const { report, isLoading: reportLoading, isError: reportError } = useMorningReport()
  const { news, isLoading: newsLoading, isError: newsError } = useLatestNews()
  const { hotStocks, isLoading: hotLoading } = useHotStocks()

  const [aiResults, setAiResults] = useState<AiSentimentResult[] | null>(null)
  const [aiLoading, setAiLoading] = useState(false)
  const [aiError, setAiError] = useState<string | null>(null)

  async function handleAiAnalysis() {
    if (!news?.length) return
    setAiLoading(true)
    setAiError(null)
    try {
      const payload: AiSentimentNewsInput[] = news.map((item) => ({
        title: item.title,
        summary: '',
        link: item.url,
        source: item.source,
      }))
      const data = await fetchAPI<AiSentimentResponse>('/ai/news-sentiment', {
        method: 'POST',
        body: JSON.stringify({ news: payload }),
      }, 30000)
      setAiResults(data.results)
    } catch (err) {
      setAiError(err instanceof Error ? err.message : '分析失敗，請稍後再試')
    } finally {
      setAiLoading(false)
    }
  }

  const sentimentIcon = (s: AiSentimentResult['sentiment']) =>
    s === 'positive' ? '🟢' : s === 'negative' ? '🔴' : '⚪'

  const aiCounts = aiResults
    ? {
        positive: aiResults.filter((r) => r.sentiment === 'positive').length,
        negative: aiResults.filter((r) => r.sentiment === 'negative').length,
        neutral: aiResults.filter((r) => r.sentiment === 'neutral').length,
      }
    : null

  const aiAvgScore = aiResults?.length
    ? aiResults.reduce((sum, r) => sum + (r.score ?? 0), 0) / aiResults.length
    : null

  return (
    <div>
      {/* 頁面標題 */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold" style={{ color: 'var(--foreground)' }}>
          每日晨報
        </h1>
        <p className="text-sm mt-1" style={{ color: 'var(--muted-foreground)' }}>
          {report?.date ? formatDate(report.date, 'month-day') + ' 市場摘要' : '市場摘要與新聞'}
        </p>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* 左欄：晨報內容 */}
        <div className="xl:col-span-2 space-y-6">
          {/* 晨報摘要 */}
          <div
            className="rounded-lg p-5"
            style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
          >
            <h2 className="text-sm font-semibold mb-3" style={{ color: 'var(--foreground)' }}>
              今日摘要
            </h2>
            {reportLoading ? (
              <div className="space-y-2">
                {[...Array(4)].map((_, i) => (
                  <Skeleton key={i} className="h-4" style={{ background: 'var(--secondary)', width: `${80 + (i % 3) * 10}%` }} />
                ))}
              </div>
            ) : reportError ? (
              <p className="text-sm" style={{ color: 'var(--muted-foreground)' }}>
                無法載入晨報內容
              </p>
            ) : (
              <>
                <p className="text-sm leading-relaxed" style={{ color: 'var(--foreground)' }}>
                  {report?.summary}
                </p>
                {report?.keyPoints?.length ? (
                  <ul className="mt-4 space-y-2">
                    {report.keyPoints.map((point, i) => (
                      <li key={i} className="flex items-start gap-2 text-sm">
                        <span style={{ color: 'var(--primary)' }} className="mt-0.5">•</span>
                        <span style={{ color: 'var(--foreground)' }}>{point}</span>
                      </li>
                    ))}
                  </ul>
                ) : null}
                {report?.marketOutlook && (
                  <div
                    className="mt-4 p-3 rounded-md"
                    style={{ background: 'var(--secondary)', borderLeft: '3px solid var(--primary)' }}
                  >
                    <p className="text-xs font-semibold mb-1" style={{ color: 'var(--primary)' }}>
                      市場展望
                    </p>
                    <p className="text-sm" style={{ color: 'var(--foreground)' }}>
                      {report.marketOutlook}
                    </p>
                  </div>
                )}
              </>
            )}
          </div>

          {/* 最新新聞 */}
          <div
            className="rounded-lg overflow-hidden"
            style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
          >
            <div className="px-5 py-3 border-b" style={{ borderColor: 'var(--border)' }}>
              <h2 className="text-sm font-semibold" style={{ color: 'var(--foreground)' }}>
                最新新聞
              </h2>
            </div>
            <div className="divide-y" style={{ borderColor: 'var(--border)' }}>
              {newsLoading
                ? [...Array(6)].map((_, i) => (
                    <div key={i} className="px-5 py-4 space-y-2">
                      <Skeleton className="h-4 w-4/5" style={{ background: 'var(--secondary)' }} />
                      <Skeleton className="h-3 w-1/3" style={{ background: 'var(--secondary)' }} />
                    </div>
                  ))
                : newsError
                ? (
                  <div className="px-5 py-8">
                    <EmptyState title="無法載入新聞" icon="!" />
                  </div>
                )
                : news?.length
                ? news.map((item) => (
                    <a
                      key={item.id}
                      href={item.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="block px-5 py-4 transition-colors hover:bg-white/5"
                    >
                      <p className="text-sm font-medium line-clamp-2" style={{ color: 'var(--foreground)' }}>
                        {item.title}
                      </p>
                      <div className="flex items-center gap-3 mt-1.5">
                        <span className="text-xs" style={{ color: 'var(--primary)' }}>
                          {item.source}
                        </span>
                        <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
                          {item.category}
                        </span>
                        <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
                          {formatDate(item.publishedAt)}
                        </span>
                      </div>
                    </a>
                  ))
                : (
                  <div className="px-5 py-8">
                    <EmptyState title="暫無最新新聞" icon="+" />
                  </div>
                )}
            </div>
          </div>

          {/* AI 情緒分析 */}
          <div
            className="rounded-lg overflow-hidden"
            style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
          >
            <div
              className="px-5 py-3 border-b flex items-center justify-between"
              style={{ borderColor: 'var(--border)' }}
            >
              <h2 className="text-sm font-semibold" style={{ color: 'var(--foreground)' }}>
                AI 情緒分析
              </h2>
              <button
                onClick={handleAiAnalysis}
                disabled={aiLoading || newsLoading || !news?.length}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-opacity disabled:opacity-50"
                style={{
                  background: 'var(--primary)',
                  color: 'var(--primary-foreground)',
                }}
              >
                {aiLoading ? (
                  <>
                    <span className="animate-spin inline-block w-3 h-3 border border-current border-t-transparent rounded-full" />
                    分析中…
                  </>
                ) : (
                  '🤖 AI 情緒分析'
                )}
              </button>
            </div>

            <div className="px-5 py-4">
              {aiError && (
                <p className="text-sm" style={{ color: 'var(--stock-down)' }}>
                  {aiError}
                </p>
              )}

              {!aiResults && !aiLoading && !aiError && (
                <p className="text-sm" style={{ color: 'var(--muted-foreground)' }}>
                  點擊按鈕，讓 AI 分析目前新聞的市場情緒。
                </p>
              )}

              {aiResults && (
                <>
                  {/* 統計摘要 */}
                  <div className="flex items-center gap-4 mb-4 flex-wrap">
                    <div
                      className="flex items-center gap-2 px-3 py-2 rounded-md text-sm"
                      style={{ background: 'var(--secondary)' }}
                    >
                      <span>🟢</span>
                      <span style={{ color: 'var(--foreground)' }}>
                        正面 <span className="font-bold">{aiCounts?.positive}</span>
                      </span>
                    </div>
                    <div
                      className="flex items-center gap-2 px-3 py-2 rounded-md text-sm"
                      style={{ background: 'var(--secondary)' }}
                    >
                      <span>🔴</span>
                      <span style={{ color: 'var(--foreground)' }}>
                        負面 <span className="font-bold">{aiCounts?.negative}</span>
                      </span>
                    </div>
                    <div
                      className="flex items-center gap-2 px-3 py-2 rounded-md text-sm"
                      style={{ background: 'var(--secondary)' }}
                    >
                      <span>⚪</span>
                      <span style={{ color: 'var(--foreground)' }}>
                        中性 <span className="font-bold">{aiCounts?.neutral}</span>
                      </span>
                    </div>
                    {aiAvgScore !== null && (
                      <div
                        className="flex items-center gap-2 px-3 py-2 rounded-md text-sm"
                        style={{ background: 'var(--secondary)' }}
                      >
                        <span style={{ color: 'var(--muted-foreground)' }}>平均分數</span>
                        <span
                          className="font-bold"
                          style={{
                            color:
                              aiAvgScore > 0
                                ? 'var(--stock-up)'
                                : aiAvgScore < 0
                                ? 'var(--stock-down)'
                                : 'var(--stock-flat)',
                          }}
                        >
                          {aiAvgScore > 0 ? '+' : ''}
                          {aiAvgScore.toFixed(2)}
                        </span>
                      </div>
                    )}
                  </div>

                  {/* 逐則結果 */}
                  <div className="space-y-3">
                    {aiResults.map((result, i) => (
                      <div
                        key={i}
                        className="rounded-md p-3"
                        style={{ background: 'var(--secondary)' }}
                      >
                        <div className="flex items-start gap-2">
                          <span className="mt-0.5 text-base leading-none">
                            {sentimentIcon(result.sentiment)}
                          </span>
                          <div className="flex-1 min-w-0">
                            <a
                              href={result.link}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-sm font-medium line-clamp-2 hover:underline"
                              style={{ color: 'var(--foreground)' }}
                            >
                              {result.title}
                            </a>
                            <div className="flex items-center gap-3 mt-1">
                              <span className="text-xs" style={{ color: 'var(--primary)' }}>
                                {result.source}
                              </span>
                              <span
                                className="text-xs font-semibold tabular-nums"
                                style={{
                                  color:
                                    (result.score ?? 0) > 0
                                      ? 'var(--stock-up)'
                                      : (result.score ?? 0) < 0
                                      ? 'var(--stock-down)'
                                      : 'var(--stock-flat)',
                                }}
                              >
                                {(result.score ?? 0) > 0 ? '+' : ''}
                                {(result.score ?? 0).toFixed(2)}
                              </span>
                            </div>
                            {result.impact && (
                              <p
                                className="text-xs mt-1 leading-relaxed"
                                style={{ color: 'var(--muted-foreground)' }}
                              >
                                {result.impact}
                              </p>
                            )}
                            {result.related_stocks?.length > 0 && (
                              <div className="flex flex-wrap gap-1 mt-1.5">
                                {result.related_stocks.map((s) => (
                                  <span
                                    key={s}
                                    className="text-xs px-1.5 py-0.5 rounded"
                                    style={{
                                      background: 'var(--card)',
                                      color: 'var(--primary)',
                                      border: '1px solid var(--border)',
                                    }}
                                  >
                                    {s}
                                  </span>
                                ))}
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </div>
          </div>
        </div>

        {/* 右欄：熱門股 */}
        <div className="xl:col-span-1">
          <div
            className="rounded-lg overflow-hidden sticky top-4"
            style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
          >
            <div className="px-5 py-3 border-b" style={{ borderColor: 'var(--border)' }}>
              <h2 className="text-sm font-semibold" style={{ color: 'var(--foreground)' }}>
                社群熱門股
              </h2>
            </div>
            <div className="divide-y" style={{ borderColor: 'var(--border)' }}>
              {hotLoading
                ? [...Array(8)].map((_, i) => (
                    <div key={i} className="px-5 py-3 flex items-center justify-between">
                      <div className="space-y-1">
                        <Skeleton className="h-4 w-16" style={{ background: 'var(--secondary)' }} />
                        <Skeleton className="h-3 w-10" style={{ background: 'var(--secondary)' }} />
                      </div>
                      <Skeleton className="h-5 w-12" style={{ background: 'var(--secondary)' }} />
                    </div>
                  ))
                : hotStocks?.length
                ? hotStocks.map((stock, i) => (
                    <div key={stock.code} className="px-5 py-3 flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <span
                          className="text-xs font-bold w-5 text-center"
                          style={{ color: 'var(--muted-foreground)' }}
                        >
                          {i + 1}
                        </span>
                        <div>
                          <p className="text-sm font-semibold" style={{ color: 'var(--foreground)' }}>
                            {stock.code}
                          </p>
                          <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
                            {stock.name}
                          </p>
                        </div>
                      </div>
                      <div className="text-right">
                        <p
                          className="text-sm font-semibold tabular-nums"
                          style={{ color: getChangeColorVar(stock.changePercent) }}
                        >
                          {formatPercent(stock.changePercent)}
                        </p>
                        <SentimentBadge sentiment={stock.sentiment} />
                      </div>
                    </div>
                  ))
                : (
                  <div className="px-5 py-8">
                    <EmptyState title="暫無熱門股資料" icon="+" />
                  </div>
                )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
