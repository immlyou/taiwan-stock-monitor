'use client'

import { useState } from 'react'
import useSWR from 'swr'
import { fetchAPI } from '@/lib/api/client'
import { KpiCard } from '@/components/shared/KpiCard'
import { StockInput } from '@/components/shared/StockInput'

interface RiskMetrics {
  var_95: number
  var_99: number
  cvar_95: number
  cvar_99: number
  volatility: number
  downside_volatility: number
  max_drawdown: number
  beta: number
  tracking_error: number
}

interface RiskResponse {
  stock_id: string
  days: number
  date_range: { start: string; end: string }
  risk_metrics: RiskMetrics
}

interface PortfolioRisk {
  days: number
  holdings: number
  portfolio_risk: {
    var_95: number | null
    var_99: number | null
    weighted_volatility: number
    max_drawdown: number
    peak_date?: string
    trough_date?: string
  }
  stock_risks: Array<{
    stock_id: string
    weight: number
    volatility: number
    var_95: number
    max_drawdown: number
  }>
}

type TabType = 'stock' | 'portfolio'

export default function RiskPage() {
  const [tab, setTab] = useState<TabType>('stock')
  const [stockCode, setStockCode] = useState('')
  const [portfolioInput, setPortfolioInput] = useState('')
  const [portfolioCodes, setPortfolioCodes] = useState('')

  const { data: stockRisk, isLoading: stockLoading, error: stockError } = useSWR<RiskResponse>(
    stockCode ? `/risk/stock/${stockCode}` : null,
    fetchAPI
  )

  const { data: portRisk, isLoading: portLoading, error: portError } = useSWR<PortfolioRisk>(
    tab === 'portfolio' && portfolioCodes
      ? ['risk-portfolio', portfolioCodes]
      : null,
    () => {
      const codes = portfolioCodes.split(',').map(c => c.trim()).filter(Boolean)
      const weight = 1 / codes.length
      return fetchAPI<PortfolioRisk>('/risk/portfolio', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          holdings: codes.map(stock_id => ({ stock_id, weight })),
        }),
      })
    }
  )

  const handlePortfolioSearch = () => {
    const codes = portfolioInput.trim()
    if (codes) setPortfolioCodes(codes)
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold" style={{ color: 'var(--foreground)' }}>風險分析</h1>
        <p className="text-sm mt-1" style={{ color: 'var(--muted-foreground)' }}>VaR/CVaR 風險量化分析</p>
      </div>

      {/* Tab */}
      <div className="flex gap-2 mb-6">
        {([{ key: 'stock', label: '個股風險' }, { key: 'portfolio', label: '組合風險' }] as const).map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className="px-5 py-2 rounded-md text-sm font-medium transition-colors"
            style={{
              background: tab === t.key ? 'var(--primary)' : 'var(--secondary)',
              color: tab === t.key ? 'var(--primary-foreground)' : 'var(--foreground)',
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'stock' && (
        <div className="space-y-4">
          {/* 輸入 */}
          <div
            className="rounded-lg p-4"
            style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
          >
            <StockInput
              value={stockCode}
              onChange={setStockCode}
              label="股票代號"
              placeholder="例：2330 或 台積電"
              className="max-w-xs"
            />
          </div>

          {!stockCode ? (
            <div
              className="rounded-lg p-8 text-center"
              style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
            >
              <p style={{ color: 'var(--muted-foreground)' }}>請輸入股票代號計算風險指標</p>
            </div>
          ) : stockError ? (
            <div className="rounded-lg p-6 text-center" style={{ background: 'var(--card)', border: '1px solid var(--border)' }}>
              <p style={{ color: 'var(--destructive)' }}>風險資料載入失敗</p>
            </div>
          ) : stockLoading ? (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {[...Array(8)].map((_, i) => (
                <KpiCard key={i} title="" value="" isLoading />
              ))}
            </div>
          ) : stockRisk ? (
            <>
              <div className="flex items-center gap-2 mb-2">
                <h2 className="text-lg font-semibold" style={{ color: 'var(--foreground)' }}>
                  {stockRisk.stock_id}
                </h2>
                <span className="text-sm" style={{ color: 'var(--muted-foreground)' }}>
                  分析期間：{stockRisk.date_range.start} ~ {stockRisk.date_range.end}（{stockRisk.days} 日）
                </span>
              </div>

              {/* KPI 卡片 */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <KpiCard
                  title="VaR 95% (日)"
                  value={`${stockRisk.risk_metrics.var_95.toFixed(2)}%`}
                  subValue="95% 信心水準"
                  accentColor="var(--destructive)"
                />
                <KpiCard
                  title="VaR 99% (日)"
                  value={`${stockRisk.risk_metrics.var_99.toFixed(2)}%`}
                  subValue="99% 信心水準"
                  accentColor="#dc2626"
                />
                <KpiCard
                  title="CVaR 95%"
                  value={`${stockRisk.risk_metrics.cvar_95.toFixed(2)}%`}
                  subValue="條件風險值"
                  accentColor="#f97316"
                />
                <KpiCard
                  title="CVaR 99%"
                  value={`${stockRisk.risk_metrics.cvar_99.toFixed(2)}%`}
                  subValue="條件風險值"
                  accentColor="#f97316"
                />
                <KpiCard
                  title="Beta 係數"
                  value={stockRisk.risk_metrics.beta.toFixed(2)}
                  subValue="相對大盤波動"
                  accentColor="#8b5cf6"
                />
                <KpiCard
                  title="年化波動度"
                  value={`${stockRisk.risk_metrics.volatility.toFixed(2)}%`}
                  subValue="年化標準差"
                  accentColor="#f59e0b"
                />
                <KpiCard
                  title="下行波動度"
                  value={`${stockRisk.risk_metrics.downside_volatility.toFixed(2)}%`}
                  subValue="負報酬標準差"
                  accentColor="#f97316"
                />
                <KpiCard
                  title="最大回撤"
                  value={`${stockRisk.risk_metrics.max_drawdown.toFixed(2)}%`}
                  subValue="歷史最大跌幅"
                  accentColor="var(--stock-down)"
                />
              </div>

              {/* 風險說明 */}
              <div
                className="rounded-lg p-4"
                style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
              >
                <h3 className="text-sm font-medium mb-3" style={{ color: 'var(--muted-foreground)' }}>風險指標說明</h3>
                <div className="space-y-2 text-sm" style={{ color: 'var(--foreground)' }}>
                  <p>
                    <span className="font-medium" style={{ color: 'var(--primary)' }}>VaR（風險值）：</span>
                    在 95% 信心水準下，單日最大損失不超過 {stockRisk.risk_metrics.var_95.toFixed(2)}%；99% 水準下為 {stockRisk.risk_metrics.var_99.toFixed(2)}%
                  </p>
                  <p>
                    <span className="font-medium" style={{ color: '#f97316' }}>CVaR（條件風險值）：</span>
                    超越 VaR 臨界時，預期平均損失約為 {stockRisk.risk_metrics.cvar_95.toFixed(2)}%（95% 水準）
                  </p>
                  <p>
                    <span className="font-medium" style={{ color: '#8b5cf6' }}>Beta：</span>
                    {stockRisk.risk_metrics.beta > 1 ? '波動度高於大盤，高風險高報酬特性' : stockRisk.risk_metrics.beta < 1 ? '波動度低於大盤，相對穩定' : '與大盤同步波動'}
                  </p>
                </div>
              </div>
            </>
          ) : null}
        </div>
      )}

      {tab === 'portfolio' && (
        <div className="space-y-4">
          <div
            className="rounded-lg p-4"
            style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
          >
            <label className="block text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>
              投資組合股票代號（逗號分隔）
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                value={portfolioInput}
                onChange={(e) => setPortfolioInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handlePortfolioSearch()}
                placeholder="例：2330,2454,2317"
                className="flex-1 h-9 rounded-md border px-3 text-sm"
                style={{ background: 'var(--background)', border: '1px solid var(--border)', color: 'var(--foreground)' }}
              />
              <button
                onClick={handlePortfolioSearch}
                className="h-9 px-4 rounded-md text-sm font-medium"
                style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}
              >
                計算組合風險
              </button>
            </div>
          </div>

          {!portfolioCodes ? (
            <div
              className="rounded-lg p-8 text-center"
              style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
            >
              <p style={{ color: 'var(--muted-foreground)' }}>請輸入投資組合股票代號</p>
            </div>
          ) : portError ? (
            <div className="rounded-lg p-6 text-center" style={{ background: 'var(--card)', border: '1px solid var(--border)' }}>
              <p style={{ color: 'var(--destructive)' }}>組合風險計算失敗</p>
            </div>
          ) : portLoading ? (
            <div className="rounded-lg p-8 text-center" style={{ background: 'var(--card)', border: '1px solid var(--border)' }}>
              <p style={{ color: 'var(--muted-foreground)' }}>計算組合風險中...</p>
            </div>
          ) : portRisk ? (
            <div className="space-y-4">
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                <KpiCard title="組合 VaR 95%" value={portRisk.portfolio_risk.var_95 != null ? `${portRisk.portfolio_risk.var_95.toFixed(2)}%` : 'N/A'} accentColor="var(--destructive)" />
                <KpiCard title="組合 VaR 99%" value={portRisk.portfolio_risk.var_99 != null ? `${portRisk.portfolio_risk.var_99.toFixed(2)}%` : 'N/A'} accentColor="#dc2626" />
                <KpiCard title="年化波動率" value={`${portRisk.portfolio_risk.weighted_volatility.toFixed(2)}%`} accentColor="#f59e0b" />
                <KpiCard title="最大回撤" value={`${portRisk.portfolio_risk.max_drawdown.toFixed(2)}%`} accentColor="#f97316" />
                <KpiCard title="持股數" value={`${portRisk.holdings}`} accentColor="#8b5cf6" />
              </div>

              {/* 個股風險明細 */}
              {portRisk.stock_risks.length > 0 && (
                <div
                  className="rounded-lg p-4 overflow-x-auto"
                  style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
                >
                  <h3 className="text-sm font-medium mb-3" style={{ color: 'var(--muted-foreground)' }}>個股風險明細</h3>
                  <table className="text-sm w-full">
                    <thead>
                      <tr style={{ borderBottom: '1px solid var(--border)' }}>
                        <th className="px-3 py-2 text-left" style={{ color: 'var(--muted-foreground)' }}>代號</th>
                        <th className="px-3 py-2 text-right" style={{ color: 'var(--muted-foreground)' }}>權重</th>
                        <th className="px-3 py-2 text-right" style={{ color: 'var(--muted-foreground)' }}>年化波動</th>
                        <th className="px-3 py-2 text-right" style={{ color: 'var(--muted-foreground)' }}>VaR 95%</th>
                        <th className="px-3 py-2 text-right" style={{ color: 'var(--muted-foreground)' }}>最大回撤</th>
                      </tr>
                    </thead>
                    <tbody>
                      {portRisk.stock_risks.map((sr) => (
                        <tr key={sr.stock_id} style={{ borderBottom: '1px solid var(--border)' }}>
                          <td className="px-3 py-2 font-semibold" style={{ color: 'var(--primary)' }}>{sr.stock_id}</td>
                          <td className="px-3 py-2 text-right tabular-nums" style={{ color: 'var(--foreground)' }}>{(sr.weight * 100).toFixed(0)}%</td>
                          <td className="px-3 py-2 text-right tabular-nums" style={{ color: 'var(--foreground)' }}>{sr.volatility.toFixed(2)}%</td>
                          <td className="px-3 py-2 text-right tabular-nums" style={{ color: 'var(--stock-down)' }}>{sr.var_95.toFixed(2)}%</td>
                          <td className="px-3 py-2 text-right tabular-nums" style={{ color: 'var(--stock-down)' }}>{sr.max_drawdown.toFixed(2)}%</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          ) : null}
        </div>
      )}
    </div>
  )
}
