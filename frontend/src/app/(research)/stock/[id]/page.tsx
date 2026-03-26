'use client'

import { use, useState } from 'react'
import { useRouter } from 'next/navigation'
import useSWR from 'swr'
import { fetchAPI } from '@/lib/api/client'
import { KpiCard } from '@/components/shared/KpiCard'
import { StockInput } from '@/components/shared/StockInput'
import { formatPrice, formatPercent, getChangeColorVar } from '@/lib/utils/format'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts'

interface StockDetailPageProps {
  params: Promise<{ id: string }>
}

type TabType = 'chart' | 'technical' | 'chip' | 'basic'

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

export default function StockDetailPage({ params }: StockDetailPageProps) {
  const { id } = use(params)
  const router = useRouter()
  const [tab, setTab] = useState<TabType>('chart')

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

  const tabs: { key: TabType; label: string }[] = [
    { key: 'chart', label: '走勢圖' },
    { key: 'technical', label: '技術分析' },
    { key: 'chip', label: '籌碼' },
    { key: 'basic', label: '基本資料' },
  ]

  // OHLCV 資料，取 close 欄位畫折線
  const chartData = ohlcv?.data ?? []

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
    </div>
  )
}
