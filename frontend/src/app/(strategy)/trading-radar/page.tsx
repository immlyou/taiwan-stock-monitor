'use client'

import { useState } from 'react'
import useSWR from 'swr'
import { fetchAPI } from '@/lib/api/client'
import { StockInput } from '@/components/shared/StockInput'
import { getChangeColorVar } from '@/lib/utils/format'

interface RadarSignal {
  score: number
  reasons: string[]
}

interface RadarStock {
  stock_id: string
  name?: string
  industry?: string
  latest_price: number
  radar_score: number
  probability_score: number
  action: string
  watch_price: number
  support_price: number
  resistance_price: number
  invalidation_conditions: string[]
  reasons: string[]
  risk_flags: string[]
  signal_tags: string[]
  price_change_5d?: number | null
  price_change_20d?: number | null
  volume_ratio: number
  metrics: {
    quant_score: number
    revenue_yoy?: number | null
    revenue_mom?: number | null
    institutional_5d: number
    institutional_20d: number
    ma20: number
    ma60: number
  }
  signals: {
    accumulation: RadarSignal
    revenue_momentum: RadarSignal
    distribution_risk: RadarSignal
    entry_zone: RadarSignal
  }
}

interface RadarResponse {
  date: string
  generated_at: string
  total_scanned: number
  stocks: RadarStock[]
  categories: Record<string, RadarStock[]>
}

const CATEGORY_LABELS: Record<string, string> = {
  accumulation: '主力吸籌',
  revenue_breakout: '營收爆發未反應',
  distribution_risk: '出貨風險',
  entry_watch: '進場等待區',
  daily_watch: '今日觀察',
}

function actionColor(action: string) {
  if (action === '買進觀察') return 'var(--stock-up)'
  if (action === '等回檔' || action === '強勢續抱') return 'var(--primary)'
  if (action === '減碼觀察' || action === '高風險勿追') return 'var(--destructive)'
  return 'var(--muted-foreground)'
}

function ScoreBar({ label, score }: { label: string; score: number }) {
  return (
    <div>
      <div className="flex justify-between text-xs mb-1">
        <span style={{ color: 'var(--muted-foreground)' }}>{label}</span>
        <span className="tabular-nums" style={{ color: 'var(--foreground)' }}>{score.toFixed(1)}</span>
      </div>
      <div className="h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--border)' }}>
        <div className="h-full rounded-full" style={{ width: `${Math.min(100, score)}%`, background: score >= 65 ? 'var(--primary)' : 'var(--muted-foreground)' }} />
      </div>
    </div>
  )
}

function StockCard({ item, onSelect }: { item: RadarStock; onSelect?: (stockId: string) => void }) {
  return (
    <button
      onClick={() => onSelect?.(item.stock_id)}
      className="text-left rounded-lg p-4 transition-opacity hover:opacity-80"
      style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
    >
      <div className="flex items-start justify-between gap-3 mb-3">
        <div>
          <p className="font-semibold" style={{ color: 'var(--primary)' }}>{item.stock_id} {item.name ?? ''}</p>
          <p className="text-xs mt-0.5" style={{ color: 'var(--muted-foreground)' }}>{item.industry ?? '—'} / 現價 {item.latest_price.toFixed(2)}</p>
        </div>
        <span className="px-2 py-1 rounded text-xs font-semibold" style={{ background: 'var(--secondary)', color: actionColor(item.action) }}>
          {item.action}
        </span>
      </div>
      <div className="grid grid-cols-3 gap-2 mb-3">
        <div>
          <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>雷達分</p>
          <p className="text-xl font-bold tabular-nums" style={{ color: actionColor(item.action) }}>{item.radar_score.toFixed(1)}</p>
        </div>
        <div>
          <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>機率分</p>
          <p className="text-xl font-bold tabular-nums" style={{ color: 'var(--foreground)' }}>{item.probability_score.toFixed(1)}</p>
        </div>
        <div>
          <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>20日</p>
          <p className="text-xl font-bold tabular-nums" style={{ color: getChangeColorVar(item.price_change_20d ?? 0) }}>
            {item.price_change_20d != null && item.price_change_20d > 0 ? '+' : ''}{item.price_change_20d?.toFixed(1) ?? '—'}%
          </p>
        </div>
      </div>
      <div className="flex flex-wrap gap-1 mb-2">
        {item.signal_tags.map((tag) => (
          <span key={tag} className="px-2 py-0.5 rounded text-[11px]" style={{ background: 'var(--secondary)', color: 'var(--foreground)' }}>{tag}</span>
        ))}
      </div>
      <p className="text-xs line-clamp-2" style={{ color: 'var(--muted-foreground)' }}>{item.reasons[0] ?? '維持觀察'}</p>
    </button>
  )
}

export default function TradingRadarPage() {
  const { data, isLoading, error } = useSWR<RadarResponse>('/radar/stocks?top_n=60', fetchAPI)
  const [selectedId, setSelectedId] = useState('2330')
  const { data: selected } = useSWR<RadarStock>(selectedId ? `/radar/stock/${selectedId}` : null, fetchAPI)

  const categories = data?.categories ?? {}
  const topStocks = data?.stocks ?? []

  return (
    <div>
      <div className="mb-6 flex flex-col md:flex-row md:items-start md:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: 'var(--foreground)' }}>AI 操盤雷達</h1>
          <p className="text-sm mt-1" style={{ color: 'var(--muted-foreground)' }}>
            籌碼、營收、技術位置與出貨風險的機率型訊號
          </p>
        </div>
        <div className="w-full md:w-72">
          <StockInput value={selectedId} onChange={setSelectedId} placeholder="輸入個股代號" />
        </div>
      </div>

      {error ? (
        <div className="rounded-lg p-6 text-center" style={{ background: 'var(--card)', border: '1px solid var(--border)', color: 'var(--destructive)' }}>
          雷達資料載入失敗
        </div>
      ) : isLoading ? (
        <div className="grid md:grid-cols-3 gap-3">
          {[...Array(6)].map((_, i) => <div key={i} className="h-40 rounded-lg animate-pulse" style={{ background: 'var(--card)' }} />)}
        </div>
      ) : (
        <div className="space-y-6">
          {selected && (
            <div className="rounded-lg p-4" style={{ background: 'var(--card)', border: '1px solid var(--border)' }}>
              <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4 mb-4">
                <div>
                  <h2 className="text-lg font-semibold" style={{ color: 'var(--foreground)' }}>
                    {selected.stock_id} {selected.name} 操盤判讀
                  </h2>
                  <p className="text-xs mt-0.5" style={{ color: 'var(--muted-foreground)' }}>
                    觀察價 {selected.watch_price.toFixed(2)} / 支撐 {selected.support_price.toFixed(2)} / 壓力 {selected.resistance_price.toFixed(2)}
                  </p>
                </div>
                <span className="px-3 py-1 rounded text-sm font-semibold" style={{ background: 'var(--secondary)', color: actionColor(selected.action) }}>
                  {selected.action}
                </span>
              </div>

              <div className="grid md:grid-cols-4 gap-4 mb-4">
                <ScoreBar label="主力吸籌" score={selected.signals.accumulation.score} />
                <ScoreBar label="營收動能" score={selected.signals.revenue_momentum.score} />
                <ScoreBar label="進場等待區" score={selected.signals.entry_zone.score} />
                <ScoreBar label="出貨風險" score={selected.signals.distribution_risk.score} />
              </div>

              <div className="grid md:grid-cols-3 gap-3">
                <div className="rounded-md p-3" style={{ background: 'var(--secondary)' }}>
                  <p className="text-xs mb-2" style={{ color: 'var(--muted-foreground)' }}>推薦理由</p>
                  <div className="space-y-1">
                    {selected.reasons.slice(0, 4).map((reason) => (
                      <p key={reason} className="text-sm" style={{ color: 'var(--foreground)' }}>{reason}</p>
                    ))}
                  </div>
                </div>
                <div className="rounded-md p-3" style={{ background: 'var(--secondary)' }}>
                  <p className="text-xs mb-2" style={{ color: 'var(--muted-foreground)' }}>風險警訊</p>
                  <div className="space-y-1">
                    {(selected.risk_flags.length ? selected.risk_flags : ['目前無明顯出貨警訊']).map((risk) => (
                      <p key={risk} className="text-sm" style={{ color: selected.risk_flags.length ? 'var(--destructive)' : 'var(--foreground)' }}>{risk}</p>
                    ))}
                  </div>
                </div>
                <div className="rounded-md p-3" style={{ background: 'var(--secondary)' }}>
                  <p className="text-xs mb-2" style={{ color: 'var(--muted-foreground)' }}>失效條件</p>
                  <div className="space-y-1">
                    {selected.invalidation_conditions.map((condition) => (
                      <p key={condition} className="text-sm" style={{ color: 'var(--foreground)' }}>{condition}</p>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}

          <div className="grid md:grid-cols-5 gap-3">
            {Object.entries(CATEGORY_LABELS).map(([key, label]) => (
              <div key={key} className="rounded-lg p-3" style={{ background: 'var(--card)', border: '1px solid var(--border)' }}>
                <p className="text-xs mb-2" style={{ color: 'var(--muted-foreground)' }}>{label}</p>
                <div className="space-y-2">
                  {(categories[key] ?? []).slice(0, 4).map((item) => (
                    <button key={`${key}-${item.stock_id}`} onClick={() => setSelectedId(item.stock_id)} className="w-full text-left">
                      <div className="flex justify-between gap-2 text-sm">
                        <span style={{ color: 'var(--foreground)' }}>{item.stock_id}</span>
                        <span className="tabular-nums" style={{ color: actionColor(item.action) }}>{item.radar_score.toFixed(0)}</span>
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>

          <div>
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-base font-semibold" style={{ color: 'var(--foreground)' }}>雷達清單</h2>
              <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
                {data?.date} / 掃描 {data?.total_scanned ?? 0} 檔
              </span>
            </div>
            <div className="grid md:grid-cols-3 gap-3">
              {topStocks.slice(0, 24).map((item) => (
                <StockCard key={item.stock_id} item={item} onSelect={setSelectedId} />
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
