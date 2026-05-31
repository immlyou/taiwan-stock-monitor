'use client'

import { useState } from 'react'
import { fetchAPI } from '@/lib/api/client'
import { KpiCard } from '@/components/shared/KpiCard'

// ─── Types ───────────────────────────────────────────────────────────────────

interface Anomaly {
  stock_id: string
  name: string
  anomaly_type: string
  severity: 'high' | 'medium' | 'low'
  description: string
  values?: Record<string, number | string>
}

interface AnomalyResponse {
  anomalies: Anomaly[]
  explanation?: string
  total: number
  high_count: number
  medium_count: number
}

type Scope = 'watchlist' | 'market'

// ─── Helpers ─────────────────────────────────────────────────────────────────

const SEVERITY_CONFIG: Record<string, { icon: string; label: string; color: string; bg: string }> = {
  high: {
    icon: '🔴',
    label: '高風險',
    color: 'var(--rating-f)',
    bg: 'color-mix(in srgb, var(--rating-f) 9%, transparent)',
  },
  medium: {
    icon: '🟡',
    label: '中風險',
    color: 'var(--rating-c)',
    bg: 'color-mix(in srgb, var(--rating-c) 9%, transparent)',
  },
  low: {
    icon: '🟢',
    label: '低風險',
    color: 'var(--rating-a)',
    bg: 'color-mix(in srgb, var(--rating-a) 9%, transparent)',
  },
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

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function AiAnomalyPage() {
  const [scope, setScope] = useState<Scope>('watchlist')
  const [explain, setExplain] = useState(true)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [data, setData] = useState<AnomalyResponse | null>(null)

  async function handleScan() {
    setLoading(true)
    setError(null)
    setData(null)
    try {
      const params = new URLSearchParams({ scope, explain: String(explain) })
      const result = await fetchAPI<AnomalyResponse>(`/ai/anomalies?${params}`, undefined, 60000)
      setData(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : '掃描失敗，請稍後再試')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold" style={{ color: 'var(--foreground)' }}>
          AI 異常警報
        </h1>
        <p className="text-sm mt-1" style={{ color: 'var(--muted-foreground)' }}>
          透過 AI 模型掃描市場異常訊號，即早發現潛在風險與機會
        </p>
      </div>

      {/* Controls */}
      <Card className="p-4 mb-5">
        <div className="flex flex-wrap items-center gap-4">
          {/* Scope selector */}
          <div className="flex items-center gap-2">
            <span className="text-sm" style={{ color: 'var(--muted-foreground)' }}>
              掃描範圍
            </span>
            <div
              className="flex gap-1 p-1 rounded-lg"
              style={{ background: 'var(--secondary)' }}
            >
              {(
                [
                  { value: 'watchlist', label: '自選股' },
                  { value: 'market', label: '全市場' },
                ] as { value: Scope; label: string }[]
              ).map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => setScope(opt.value)}
                  className="px-4 py-1.5 rounded-md text-sm font-medium transition-colors"
                  style={{
                    background: scope === opt.value ? 'var(--card)' : 'transparent',
                    color:
                      scope === opt.value ? 'var(--foreground)' : 'var(--muted-foreground)',
                    boxShadow:
                      scope === opt.value ? '0 1px 3px rgba(0,0,0,0.3)' : 'none',
                  }}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          {/* AI explanation toggle */}
          <label className="flex items-center gap-2 cursor-pointer select-none">
            <div
              className="relative w-10 h-5 rounded-full transition-colors"
              style={{ background: explain ? 'var(--primary)' : 'var(--border)' }}
              onClick={() => setExplain((v) => !v)}
            >
              <span
                className="absolute top-0.5 left-0.5 w-4 h-4 rounded-full transition-transform"
                style={{
                  background: 'var(--primary-foreground)',
                  transform: explain ? 'translateX(20px)' : 'translateX(0)',
                }}
              />
            </div>
            <span className="text-sm" style={{ color: 'var(--foreground)' }}>
              AI 說明
            </span>
          </label>

          {/* Scan button */}
          <button
            onClick={handleScan}
            disabled={loading}
            className="ml-auto px-6 py-2 rounded-md text-sm font-semibold transition-opacity"
            style={{
              background: 'var(--primary)',
              color: 'var(--primary-foreground)',
              opacity: loading ? 0.6 : 1,
              cursor: loading ? 'not-allowed' : 'pointer',
            }}
          >
            {loading ? '掃描中...' : '開始掃描'}
          </button>
        </div>
      </Card>

      {/* Error */}
      {error && (
        <Card className="p-6 mb-5 text-center">
          <p className="text-sm" style={{ color: 'var(--destructive)' }}>
            {error}
          </p>
        </Card>
      )}

      {/* Results */}
      {data && (
        <div className="space-y-5">
          {/* KPI Cards */}
          <div className="grid grid-cols-3 gap-4">
            <KpiCard title="異常總數" value={String(data.total)} />
            <KpiCard title="高風險" value={String(data.high_count)} accentColor="var(--rating-f)" />
            <KpiCard title="中風險" value={String(data.medium_count)} accentColor="var(--rating-c)" />
          </div>

          {/* AI Explanation */}
          {data.explanation && (
            <div
              className="rounded-lg p-4"
              style={{
                background: 'color-mix(in srgb, var(--flow-foreign) 6%, transparent)',
                border: '1px solid color-mix(in srgb, var(--flow-foreign) 19%, transparent)',
              }}
            >
              <div className="flex items-start gap-3">
                <span className="text-lg mt-0.5">🤖</span>
                <div>
                  <p
                    className="text-xs font-semibold mb-1"
                    style={{ color: 'var(--flow-foreign)' }}
                  >
                    AI 綜合說明
                  </p>
                  <p className="text-sm leading-relaxed" style={{ color: 'var(--foreground)' }}>
                    {data.explanation}
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Anomaly List */}
          {data.anomalies.length === 0 ? (
            <Card className="p-8 text-center">
              <p className="text-sm" style={{ color: 'var(--muted-foreground)' }}>
                未發現異常訊號
              </p>
            </Card>
          ) : (
            <Card className="overflow-hidden">
              <div
                className="px-4 py-3 border-b"
                style={{ borderColor: 'var(--border)' }}
              >
                <h3 className="text-sm font-medium" style={{ color: 'var(--foreground)' }}>
                  異常清單 — 共 {data.anomalies.length} 筆
                </h3>
              </div>
              <div className="divide-y" style={{ borderColor: 'var(--border)' }}>
                {data.anomalies.map((item, i) => {
                  const sev = SEVERITY_CONFIG[item.severity] ?? SEVERITY_CONFIG.medium
                  return (
                    <div key={`${item.stock_id}-${i}`} className="px-4 py-4">
                      <div className="flex items-start gap-3">
                        {/* Severity icon */}
                        <span className="text-xl mt-0.5 leading-none">{sev.icon}</span>

                        <div className="flex-1 min-w-0">
                          {/* Top row */}
                          <div className="flex flex-wrap items-center gap-2 mb-1">
                            <span
                              className="text-sm font-semibold tabular-nums"
                              style={{ color: 'var(--primary)' }}
                            >
                              {item.stock_id}
                            </span>
                            <span
                              className="text-sm font-medium"
                              style={{ color: 'var(--foreground)' }}
                            >
                              {item.name}
                            </span>
                            {/* Anomaly type badge */}
                            <span
                              className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium"
                              style={{
                                background: 'var(--secondary)',
                                color: 'var(--muted-foreground)',
                              }}
                            >
                              {item.anomaly_type}
                            </span>
                            {/* Severity badge */}
                            <span
                              className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold"
                              style={{ background: sev.bg, color: sev.color }}
                            >
                              {sev.label}
                            </span>
                          </div>

                          {/* Description */}
                          <p
                            className="text-sm leading-relaxed"
                            style={{ color: 'var(--muted-foreground)' }}
                          >
                            {item.description}
                          </p>

                          {/* Values */}
                          {item.values && Object.keys(item.values).length > 0 && (
                            <div className="flex flex-wrap gap-3 mt-2">
                              {Object.entries(item.values).map(([k, v]) => (
                                <span
                                  key={k}
                                  className="text-xs tabular-nums"
                                  style={{ color: 'var(--muted-foreground)' }}
                                >
                                  <span style={{ color: 'var(--foreground)' }}>{k}</span>
                                  {' '}
                                  <span className="font-semibold" style={{ color: 'var(--foreground)' }}>
                                    {v}
                                  </span>
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            </Card>
          )}
        </div>
      )}

      {/* Empty state (before first scan) */}
      {!data && !loading && !error && (
        <Card className="p-12 text-center">
          <p className="text-3xl mb-3">🔍</p>
          <p className="text-sm font-medium mb-1" style={{ color: 'var(--foreground)' }}>
            尚未掃描
          </p>
          <p className="text-sm" style={{ color: 'var(--muted-foreground)' }}>
            選擇掃描範圍後點擊「開始掃描」
          </p>
        </Card>
      )}
    </div>
  )
}
