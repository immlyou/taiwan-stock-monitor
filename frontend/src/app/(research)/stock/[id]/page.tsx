'use client'

import { use, useState } from 'react'
import useSWR from 'swr'
import { fetchAPI } from '@/lib/api/client'
import { KpiCard } from '@/components/shared/KpiCard'
import { formatPrice, formatPercent, formatVolume, getChangeColorVar } from '@/lib/utils/format'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts'

interface StockDetailPageProps {
  params: Promise<{ id: string }>
}

type TabType = 'chart' | 'technical' | 'chip' | 'basic'

interface StockDetail {
  code: string
  name: string
  close: number
  change: number
  changePercent: number
  open: number
  high: number
  low: number
  volume: number
  pe?: number
  pb?: number
  dividendYield?: number
  marketCap?: number
}

interface TechnicalData {
  priceHistory?: Array<{ date: string; close: number; volume: number }>
  indicators?: {
    ma5?: number; ma10?: number; ma20?: number; ma60?: number
    rsi14?: number; macd?: number; macdSignal?: number
    kdK?: number; kdD?: number
    bollUpper?: number; bollMiddle?: number; bollLower?: number
  }
}

interface ChipData {
  foreign?: { buy: number; sell: number; net: number }
  investmentTrust?: { buy: number; sell: number; net: number }
  dealer?: { buy: number; sell: number; net: number }
  marginBalance?: number
  shortBalance?: number
}

export default function StockDetailPage({ params }: StockDetailPageProps) {
  const { id } = use(params)
  const [tab, setTab] = useState<TabType>('chart')

  const { data: stock, isLoading: stockLoading } = useSWR<StockDetail>(
    `/stocks/${id}`,
    fetchAPI
  )

  const { data: technical } = useSWR<TechnicalData>(
    tab === 'technical' || tab === 'chart' ? `/stocks/${id}/technical` : null,
    fetchAPI
  )

  const { data: chip } = useSWR<ChipData>(
    tab === 'chip' ? `/stocks/${id}/chip` : null,
    fetchAPI
  )

  const tabs: { key: TabType; label: string }[] = [
    { key: 'chart', label: '走勢圖' },
    { key: 'technical', label: '技術分析' },
    { key: 'chip', label: '籌碼' },
    { key: 'basic', label: '基本資料' },
  ]

  const priceHistory = (technical as { priceHistory?: Array<{ date: string; close: number }> })?.priceHistory ?? []

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold" style={{ color: 'var(--foreground)' }}>
          {stock ? `${stock.code} ${stock.name}` : `個股分析 — ${id}`}
        </h1>
        <p className="text-sm mt-1" style={{ color: 'var(--muted-foreground)' }}>個股詳細分析</p>
      </div>

      {/* KPI 列 */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
        <KpiCard
          title="現價"
          value={stock ? formatPrice(stock.close) : '—'}
          change={stock?.change}
          changeLabel={stock ? formatPercent(stock.changePercent) : undefined}
          isLoading={stockLoading}
          accentColor="var(--primary)"
        />
        <KpiCard
          title="開盤"
          value={stock ? formatPrice(stock.open) : '—'}
          isLoading={stockLoading}
          accentColor="var(--muted-foreground)"
        />
        <KpiCard
          title="本益比 PE"
          value={stock?.pe != null ? stock.pe.toFixed(2) : '—'}
          isLoading={stockLoading}
          accentColor="#8b5cf6"
        />
        <KpiCard
          title="股價淨值比 PB"
          value={stock?.pb != null ? stock.pb.toFixed(2) : '—'}
          isLoading={stockLoading}
          accentColor="#f59e0b"
        />
        <KpiCard
          title="殖利率"
          value={stock?.dividendYield != null ? `${stock.dividendYield.toFixed(2)}%` : '—'}
          isLoading={stockLoading}
          accentColor="var(--stock-down)"
        />
      </div>

      {/* 今日行情 */}
      {stock && (
        <div
          className="rounded-lg p-4 mb-6 flex flex-wrap gap-6"
          style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
        >
          <div>
            <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>最高</span>
            <p className="font-semibold" style={{ color: 'var(--stock-up)' }}>{formatPrice(stock.high)}</p>
          </div>
          <div>
            <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>最低</span>
            <p className="font-semibold" style={{ color: 'var(--stock-down)' }}>{formatPrice(stock.low)}</p>
          </div>
          <div>
            <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>成交量</span>
            <p className="font-semibold" style={{ color: 'var(--foreground)' }}>{formatVolume(stock.volume)}</p>
          </div>
          {stock.marketCap && (
            <div>
              <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>市值</span>
              <p className="font-semibold" style={{ color: 'var(--foreground)' }}>
                {(stock.marketCap / 1e8).toFixed(0)} 億
              </p>
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
          {tab === 'chart' && (
            <div>
              <h3 className="text-sm font-medium mb-4" style={{ color: 'var(--muted-foreground)' }}>
                近期收盤走勢
              </h3>
              {priceHistory.length > 0 ? (
                <ResponsiveContainer width="100%" height={300}>
                  <LineChart data={priceHistory}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                    <XAxis dataKey="date" tick={{ fill: 'var(--muted-foreground)', fontSize: 11 }} />
                    <YAxis tick={{ fill: 'var(--muted-foreground)', fontSize: 11 }} domain={['auto', 'auto']} />
                    <Tooltip
                      contentStyle={{ background: 'var(--card)', border: '1px solid var(--border)', color: 'var(--foreground)' }}
                    />
                    <Line type="monotone" dataKey="close" stroke="var(--primary)" dot={false} strokeWidth={2} name="收盤價" />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-64 flex items-center justify-center" style={{ color: 'var(--muted-foreground)' }}>
                  載入走勢資料中...
                </div>
              )}
            </div>
          )}

          {tab === 'technical' && (
            <div className="space-y-4">
              <h3 className="text-sm font-medium" style={{ color: 'var(--muted-foreground)' }}>技術指標</h3>
              {technical?.indicators ? (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  {([
                    { label: 'MA5', value: technical.indicators.ma5 },
                    { label: 'MA10', value: technical.indicators.ma10 },
                    { label: 'MA20', value: technical.indicators.ma20 },
                    { label: 'MA60', value: technical.indicators.ma60 },
                    { label: 'RSI(14)', value: technical.indicators.rsi14 },
                    { label: 'MACD', value: technical.indicators.macd },
                    { label: 'KD-K', value: technical.indicators.kdK },
                    { label: 'KD-D', value: technical.indicators.kdD },
                    { label: '布林上軌', value: technical.indicators.bollUpper },
                    { label: '布林中軌', value: technical.indicators.bollMiddle },
                    { label: '布林下軌', value: technical.indicators.bollLower },
                  ] as { label: string; value?: number }[]).filter(i => i.value != null).map((item) => (
                    <div
                      key={item.label}
                      className="rounded-md p-3"
                      style={{ background: 'var(--secondary)' }}
                    >
                      <p className="text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>{item.label}</p>
                      <p className="font-semibold tabular-nums" style={{ color: 'var(--foreground)' }}>
                        {item.value!.toFixed(2)}
                      </p>
                    </div>
                  ))}
                </div>
              ) : (
                <p style={{ color: 'var(--muted-foreground)' }}>載入技術指標中...</p>
              )}
            </div>
          )}

          {tab === 'chip' && (
            <div className="space-y-4">
              <h3 className="text-sm font-medium" style={{ color: 'var(--muted-foreground)' }}>三大法人買賣超</h3>
              {chip ? (
                <>
                  <table className="w-full text-sm">
                    <thead>
                      <tr style={{ borderBottom: '1px solid var(--border)' }}>
                        {['法人', '買進', '賣出', '買賣超'].map((h) => (
                          <th key={h} className="text-left py-2 px-3" style={{ color: 'var(--muted-foreground)' }}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {([
                        { label: '外資', data: chip.foreign },
                        { label: '投信', data: chip.investmentTrust },
                        { label: '自營商', data: chip.dealer },
                      ] as { label: string; data?: { buy: number; sell: number; net: number } }[]).filter(r => r.data).map(({ label, data }) => (
                        <tr key={label} style={{ borderBottom: '1px solid var(--border)' }}>
                          <td className="py-2 px-3" style={{ color: 'var(--foreground)' }}>{label}</td>
                          <td className="py-2 px-3 tabular-nums" style={{ color: 'var(--stock-up)' }}>
                            {data!.buy.toLocaleString()}
                          </td>
                          <td className="py-2 px-3 tabular-nums" style={{ color: 'var(--stock-down)' }}>
                            {data!.sell.toLocaleString()}
                          </td>
                          <td
                            className="py-2 px-3 font-semibold tabular-nums"
                            style={{ color: getChangeColorVar(data!.net) }}
                          >
                            {data!.net > 0 ? '+' : ''}{data!.net.toLocaleString()}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <div className="grid grid-cols-2 gap-3 mt-4">
                    <div className="rounded-md p-3" style={{ background: 'var(--secondary)' }}>
                      <p className="text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>融資餘額</p>
                      <p className="font-semibold" style={{ color: 'var(--foreground)' }}>
                        {chip.marginBalance?.toLocaleString() ?? '—'} 張
                      </p>
                    </div>
                    <div className="rounded-md p-3" style={{ background: 'var(--secondary)' }}>
                      <p className="text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>融券餘額</p>
                      <p className="font-semibold" style={{ color: 'var(--foreground)' }}>
                        {chip.shortBalance?.toLocaleString() ?? '—'} 張
                      </p>
                    </div>
                  </div>
                </>
              ) : (
                <p style={{ color: 'var(--muted-foreground)' }}>載入籌碼資料中...</p>
              )}
            </div>
          )}

          {tab === 'basic' && (
            <div>
              <h3 className="text-sm font-medium mb-4" style={{ color: 'var(--muted-foreground)' }}>基本資料</h3>
              {stock ? (
                <table className="w-full text-sm">
                  <tbody>
                    {[
                      { label: '股票代號', value: stock.code },
                      { label: '公司名稱', value: stock.name },
                      { label: '收盤價', value: formatPrice(stock.close) },
                      { label: '本益比', value: stock.pe?.toFixed(2) ?? '—' },
                      { label: '股價淨值比', value: stock.pb?.toFixed(2) ?? '—' },
                      { label: '殖利率', value: stock.dividendYield != null ? `${stock.dividendYield.toFixed(2)}%` : '—' },
                      { label: '市值', value: stock.marketCap != null ? `${(stock.marketCap / 1e8).toFixed(0)} 億元` : '—' },
                    ].map(({ label, value }) => (
                      <tr key={label} style={{ borderBottom: '1px solid var(--border)' }}>
                        <td className="py-2 px-3 w-32" style={{ color: 'var(--muted-foreground)' }}>{label}</td>
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
    </div>
  )
}
