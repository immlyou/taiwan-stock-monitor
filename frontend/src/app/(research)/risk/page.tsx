'use client'

import { useState } from 'react'
import useSWR from 'swr'
import { fetchAPI } from '@/lib/api/client'
import { KpiCard } from '@/components/shared/KpiCard'

interface RiskData {
  code: string
  name: string
  var95: number
  var99: number
  cvar95: number
  cvar99: number
  beta: number
  sharpe: number
  maxDrawdown: number
  volatility: number
  period: string
}

interface PortfolioRisk {
  totalVar95: number
  totalVar99: number
  totalCvar95: number
  weightedBeta: number
  portfolioVolatility: number
  correlationMatrix: Array<{ code: string; values: number[] }>
  codes: string[]
}

type TabType = 'stock' | 'portfolio'

export default function RiskPage() {
  const [tab, setTab] = useState<TabType>('stock')
  const [inputCode, setInputCode] = useState('')
  const [stockCode, setStockCode] = useState('')
  const [portfolioCodes, setPortfolioCodes] = useState('')

  const { data: stockRisk, isLoading: stockLoading, error: stockError } = useSWR<RiskData>(
    stockCode ? `/risk/stock/${stockCode}` : null,
    fetchAPI
  )

  const { data: portRisk, isLoading: portLoading, error: portError } = useSWR<PortfolioRisk>(
    tab === 'portfolio' && portfolioCodes
      ? `/risk/portfolio?codes=${portfolioCodes}`
      : null,
    fetchAPI
  )

  const handleStockSearch = () => {
    const code = inputCode.trim().toUpperCase()
    if (code) setStockCode(code)
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
            <div className="flex gap-2 items-end">
              <div>
                <label className="block text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>股票代號</label>
                <input
                  type="text"
                  value={inputCode}
                  onChange={(e) => setInputCode(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleStockSearch()}
                  placeholder="例：2330"
                  className="h-9 w-36 rounded-md border px-3 text-sm"
                  style={{ background: 'var(--background)', border: '1px solid var(--border)', color: 'var(--foreground)' }}
                />
              </div>
              <button
                onClick={handleStockSearch}
                className="h-9 px-4 rounded-md text-sm font-medium"
                style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}
              >
                計算風險
              </button>
            </div>
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
                  {stockRisk.code} {stockRisk.name}
                </h2>
                <span className="text-sm" style={{ color: 'var(--muted-foreground)' }}>
                  分析期間：{stockRisk.period}
                </span>
              </div>

              {/* KPI 卡片 */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <KpiCard
                  title="VaR 95% (日)"
                  value={`${stockRisk.var95.toFixed(2)}%`}
                  subValue="95% 信心水準"
                  accentColor="var(--destructive)"
                />
                <KpiCard
                  title="VaR 99% (日)"
                  value={`${stockRisk.var99.toFixed(2)}%`}
                  subValue="99% 信心水準"
                  accentColor="#dc2626"
                />
                <KpiCard
                  title="CVaR 95%"
                  value={`${stockRisk.cvar95.toFixed(2)}%`}
                  subValue="條件風險值"
                  accentColor="#f97316"
                />
                <KpiCard
                  title="CVaR 99%"
                  value={`${stockRisk.cvar99.toFixed(2)}%`}
                  subValue="條件風險值"
                  accentColor="#f97316"
                />
                <KpiCard
                  title="Beta 係數"
                  value={stockRisk.beta.toFixed(2)}
                  subValue="相對大盤波動"
                  accentColor="#8b5cf6"
                />
                <KpiCard
                  title="Sharpe Ratio"
                  value={stockRisk.sharpe.toFixed(2)}
                  subValue="風險調整報酬"
                  accentColor="var(--primary)"
                />
                <KpiCard
                  title="最大回撤"
                  value={`${stockRisk.maxDrawdown.toFixed(2)}%`}
                  subValue="歷史最大跌幅"
                  accentColor="var(--stock-down)"
                />
                <KpiCard
                  title="年化波動度"
                  value={`${stockRisk.volatility.toFixed(2)}%`}
                  subValue="年化標準差"
                  accentColor="#f59e0b"
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
                    在 95% 信心水準下，單日最大損失不超過 {stockRisk.var95.toFixed(2)}%；99% 水準下為 {stockRisk.var99.toFixed(2)}%
                  </p>
                  <p>
                    <span className="font-medium" style={{ color: '#f97316' }}>CVaR（條件風險值）：</span>
                    超越 VaR 臨界時，預期平均損失約為 {stockRisk.cvar95.toFixed(2)}%（95% 水準）
                  </p>
                  <p>
                    <span className="font-medium" style={{ color: '#8b5cf6' }}>Beta：</span>
                    {stockRisk.beta > 1 ? '波動度高於大盤，高風險高報酬特性' : stockRisk.beta < 1 ? '波動度低於大盤，相對穩定' : '與大盤同步波動'}
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
                value={portfolioCodes}
                onChange={(e) => setPortfolioCodes(e.target.value)}
                placeholder="例：2330,2454,2317"
                className="flex-1 h-9 rounded-md border px-3 text-sm"
                style={{ background: 'var(--background)', border: '1px solid var(--border)', color: 'var(--foreground)' }}
              />
              <button
                onClick={() => setPortfolioCodes(portfolioCodes)}
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
                <KpiCard title="組合 VaR 95%" value={`${portRisk.totalVar95.toFixed(2)}%`} accentColor="var(--destructive)" />
                <KpiCard title="組合 VaR 99%" value={`${portRisk.totalVar99.toFixed(2)}%`} accentColor="#dc2626" />
                <KpiCard title="組合 CVaR 95%" value={`${portRisk.totalCvar95.toFixed(2)}%`} accentColor="#f97316" />
                <KpiCard title="加權 Beta" value={portRisk.weightedBeta.toFixed(2)} accentColor="#8b5cf6" />
                <KpiCard title="組合年化波動" value={`${portRisk.portfolioVolatility.toFixed(2)}%`} accentColor="#f59e0b" />
              </div>

              {portRisk.correlationMatrix && portRisk.codes && (
                <div
                  className="rounded-lg p-4 overflow-x-auto"
                  style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
                >
                  <h3 className="text-sm font-medium mb-3" style={{ color: 'var(--muted-foreground)' }}>相關係數矩陣</h3>
                  <table className="text-sm">
                    <thead>
                      <tr>
                        <th className="px-3 py-2" style={{ color: 'var(--muted-foreground)' }}></th>
                        {portRisk.codes.map(c => (
                          <th key={c} className="px-3 py-2" style={{ color: 'var(--muted-foreground)' }}>{c}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {portRisk.correlationMatrix.map((row) => (
                        <tr key={row.code}>
                          <td className="px-3 py-2 font-medium" style={{ color: 'var(--foreground)' }}>{row.code}</td>
                          {row.values.map((v, j) => (
                            <td
                              key={j}
                              className="px-3 py-2 tabular-nums text-center"
                              style={{
                                color: v === 1 ? 'var(--foreground)' : v > 0.7 ? 'var(--stock-up)' : v < 0 ? 'var(--stock-down)' : 'var(--foreground)',
                                fontWeight: v === 1 ? 700 : 400,
                              }}
                            >
                              {v.toFixed(2)}
                            </td>
                          ))}
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
