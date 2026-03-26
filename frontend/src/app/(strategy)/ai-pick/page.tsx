'use client'

import { useState } from 'react'
import useSWR from 'swr'
import { fetchAPI } from '@/lib/api/client'

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

type TabType = 'value' | 'growth' | 'momentum'

const TAB_LABELS: Record<TabType, string> = {
  value: '價值選股',
  growth: '成長選股',
  momentum: '動能選股',
}

export default function AiPickPage() {
  const [activeTab, setActiveTab] = useState<TabType>('value')

  const { data, isLoading, error } = useSWR<AiPickResponse>(
    '/strategy/ai-pick',
    fetchAPI
  )

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold" style={{ color: 'var(--foreground)' }}>AI 智慧選股</h1>
        <p className="text-sm mt-1" style={{ color: 'var(--muted-foreground)' }}>多策略因子選股排行</p>
      </div>

      {error ? (
        <div className="rounded-lg p-6 text-center" style={{ background: 'var(--card)', border: '1px solid var(--border)' }}>
          <p style={{ color: 'var(--destructive)' }}>AI 選股資料載入失敗</p>
        </div>
      ) : isLoading ? (
        <div className="rounded-lg p-8 text-center" style={{ background: 'var(--card)', border: '1px solid var(--border)' }}>
          <p style={{ color: 'var(--muted-foreground)' }}>載入中...</p>
        </div>
      ) : data ? (
        <div>
          {/* Tab */}
          <div className="flex gap-2 mb-4">
            {(Object.keys(TAB_LABELS) as TabType[]).map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className="px-5 py-2 rounded-md text-sm font-medium transition-colors"
                style={{
                  background: activeTab === tab ? 'var(--primary)' : 'var(--secondary)',
                  color: activeTab === tab ? 'var(--primary-foreground)' : 'var(--foreground)',
                }}
              >
                {TAB_LABELS[tab]}
                <span
                  className="ml-2 text-xs px-1.5 py-0.5 rounded-full"
                  style={{
                    background: activeTab === tab ? 'rgba(255,255,255,0.2)' : 'var(--border)',
                    color: activeTab === tab ? 'var(--primary-foreground)' : 'var(--muted-foreground)',
                  }}
                >
                  {data.strategies[tab].total}
                </span>
              </button>
            ))}
          </div>

          <div
            className="rounded-lg overflow-hidden"
            style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
          >
            <div className="px-4 py-3 border-b flex justify-between items-center" style={{ borderColor: 'var(--border)' }}>
              <h3 className="text-sm font-medium" style={{ color: 'var(--foreground)' }}>
                {TAB_LABELS[activeTab]} — 共 {data.strategies[activeTab].total} 支
              </h3>
              <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>{data.date}</span>
            </div>
            <div className="overflow-x-auto">
              {activeTab === 'value' && (
                <table className="w-full text-sm">
                  <thead>
                    <tr style={{ background: 'var(--secondary)' }}>
                      {['排名', '代號', '名稱', '現價', 'PE', 'PB', '殖利率%'].map(h => (
                        <th key={h} className="text-left py-2 px-4" style={{ color: 'var(--muted-foreground)' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {data.strategies.value.stocks.map((row, i) => (
                      <tr key={row.stock_id} style={{ borderBottom: '1px solid var(--border)' }}>
                        <td className="py-2 px-4 tabular-nums" style={{ color: 'var(--muted-foreground)' }}>{i + 1}</td>
                        <td className="py-2 px-4 font-medium" style={{ color: 'var(--primary)' }}>{row.stock_id}</td>
                        <td className="py-2 px-4" style={{ color: 'var(--foreground)' }}>{row.name}</td>
                        <td className="py-2 px-4 tabular-nums" style={{ color: 'var(--foreground)' }}>{row.price.toFixed(2)}</td>
                        <td className="py-2 px-4 tabular-nums" style={{ color: 'var(--foreground)' }}>{row.pe_ratio.toFixed(1)}</td>
                        <td className="py-2 px-4 tabular-nums" style={{ color: 'var(--foreground)' }}>{row.pb_ratio.toFixed(2)}</td>
                        <td className="py-2 px-4 tabular-nums font-semibold" style={{ color: 'var(--primary)' }}>
                          {row.dividend_yield.toFixed(2)}%
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}

              {activeTab === 'growth' && (
                <table className="w-full text-sm">
                  <thead>
                    <tr style={{ background: 'var(--secondary)' }}>
                      {['排名', '代號', '名稱', '現價', '年增率%', '月增率%'].map(h => (
                        <th key={h} className="text-left py-2 px-4" style={{ color: 'var(--muted-foreground)' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {data.strategies.growth.stocks.map((row, i) => (
                      <tr key={row.stock_id} style={{ borderBottom: '1px solid var(--border)' }}>
                        <td className="py-2 px-4 tabular-nums" style={{ color: 'var(--muted-foreground)' }}>{i + 1}</td>
                        <td className="py-2 px-4 font-medium" style={{ color: 'var(--primary)' }}>{row.stock_id}</td>
                        <td className="py-2 px-4" style={{ color: 'var(--foreground)' }}>{row.name}</td>
                        <td className="py-2 px-4 tabular-nums" style={{ color: 'var(--foreground)' }}>{row.price.toFixed(2)}</td>
                        <td className="py-2 px-4 tabular-nums font-semibold" style={{ color: 'var(--stock-up)' }}>
                          +{row.revenue_yoy.toFixed(2)}%
                        </td>
                        <td className="py-2 px-4 tabular-nums font-semibold" style={{ color: row.revenue_mom >= 0 ? 'var(--stock-up)' : 'var(--stock-down)' }}>
                          {row.revenue_mom >= 0 ? '+' : ''}{row.revenue_mom.toFixed(2)}%
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}

              {activeTab === 'momentum' && (
                <table className="w-full text-sm">
                  <thead>
                    <tr style={{ background: 'var(--secondary)' }}>
                      {['排名', '代號', '名稱', '現價', '量比', 'RSI', '突破高點'].map(h => (
                        <th key={h} className="text-left py-2 px-4" style={{ color: 'var(--muted-foreground)' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {data.strategies.momentum.stocks.map((row, i) => (
                      <tr key={row.stock_id} style={{ borderBottom: '1px solid var(--border)' }}>
                        <td className="py-2 px-4 tabular-nums" style={{ color: 'var(--muted-foreground)' }}>{i + 1}</td>
                        <td className="py-2 px-4 font-medium" style={{ color: 'var(--primary)' }}>{row.stock_id}</td>
                        <td className="py-2 px-4" style={{ color: 'var(--foreground)' }}>{row.name}</td>
                        <td className="py-2 px-4 tabular-nums" style={{ color: 'var(--foreground)' }}>{row.price.toFixed(2)}</td>
                        <td className="py-2 px-4 tabular-nums font-semibold" style={{ color: 'var(--primary)' }}>
                          {row.volume_ratio.toFixed(2)}x
                        </td>
                        <td className="py-2 px-4 tabular-nums" style={{ color: row.rsi > 70 ? 'var(--stock-down)' : row.rsi < 30 ? 'var(--stock-up)' : 'var(--foreground)' }}>
                          {row.rsi.toFixed(1)}
                        </td>
                        <td className="py-2 px-4 tabular-nums" style={{ color: 'var(--muted-foreground)' }}>
                          {row.breakout_high.toFixed(2)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
