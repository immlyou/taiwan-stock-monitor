'use client'

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

interface HotStock {
  code: string
  name: string
  mentionCount: number
  sentiment: 'positive' | 'negative' | 'neutral'
  changePercent: number
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
  const { data, error, isLoading } = useSWR<NewsItem[]>(
    '/news/latest',
    (path: string) => fetchAPI<NewsItem[]>(path),
    { refreshInterval: 60000 }
  )
  return { news: data, isLoading, isError: !!error }
}

function useHotStocks() {
  const { data, isLoading } = useSWR<HotStock[]>(
    '/social/hot-stocks',
    (path: string) => fetchAPI<HotStock[]>(path),
    { refreshInterval: 120000 }
  )
  return { hotStocks: data, isLoading }
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
