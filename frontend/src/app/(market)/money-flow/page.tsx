'use client'

import useSWR from 'swr'
import { fetchAPI } from '@/lib/api/client'
import { KpiCard } from '@/components/shared/KpiCard'
import { EmptyState } from '@/components/shared/EmptyState'
import { Skeleton } from '@/components/ui/skeleton'
import {
  formatVolumeValue,
  getChangeColorVar,
} from '@/lib/utils/format'

// 對應 GET /market/money-flow
interface InstitutionDetail {
  total_net: number
  top_buy?: Array<{ stock_id: string; name: string; net_shares: number }>
  top_sell?: Array<{ stock_id: string; name: string; net_shares: number }>
}

interface MoneyFlowData {
  date: string
  foreign: InstitutionDetail
  trust: InstitutionDetail
  dealer: InstitutionDetail
}

function useMoneyFlow() {
  const { data, error, isLoading } = useSWR<MoneyFlowData>(
    '/market/money-flow',
    (path: string) => fetchAPI<MoneyFlowData>(path),
    { refreshInterval: 60000, revalidateOnFocus: true }
  )
  return { data, isLoading, isError: !!error }
}

function TopStockTable({
  title,
  items,
  isLoading,
  colorVar,
}: {
  title: string
  items: Array<{ stock_id: string; name: string; net_shares: number }>
  isLoading: boolean
  colorVar: string
}) {
  return (
    <div>
      <h4 className="text-xs font-semibold mb-2" style={{ color: 'var(--muted-foreground)' }}>
        {title}
      </h4>
      {isLoading ? (
        <div className="space-y-1">
          {[...Array(5)].map((_, i) => (
            <Skeleton key={i} className="h-4 w-full" style={{ background: 'var(--secondary)' }} />
          ))}
        </div>
      ) : items.length > 0 ? (
        <div className="space-y-1">
          {items.slice(0, 5).map((item) => (
            <div key={item.stock_id} className="flex items-center justify-between">
              <span className="text-xs">
                <span className="font-mono font-semibold" style={{ color: 'var(--primary)' }}>
                  {item.stock_id}
                </span>
                {item.name && (
                  <span className="ml-1" style={{ color: 'var(--foreground)' }}>{item.name}</span>
                )}
              </span>
              <span className="text-xs tabular-nums font-semibold" style={{ color: colorVar }}>
                {(item.net_shares / 1000).toFixed(0)} 張
              </span>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>暫無資料</p>
      )}
    </div>
  )
}

function InstitutionCard({
  label,
  detail,
  isLoading,
}: {
  label: string
  detail?: InstitutionDetail
  isLoading: boolean
}) {
  const net = detail?.total_net ?? 0
  return (
    <div
      className="rounded-lg p-4"
      style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
    >
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold" style={{ color: 'var(--foreground)' }}>{label}</h3>
        {isLoading ? (
          <Skeleton className="h-5 w-24" style={{ background: 'var(--secondary)' }} />
        ) : (
          <span
            className="text-sm font-bold tabular-nums"
            style={{ color: getChangeColorVar(net) }}
          >
            {net > 0 ? '+' : ''}{formatVolumeValue(net)}
          </span>
        )}
      </div>
      <div className="space-y-4">
        <TopStockTable
          title="買超前五"
          items={detail?.top_buy ?? []}
          isLoading={isLoading}
          colorVar="var(--stock-up)"
        />
        <TopStockTable
          title="賣超前五"
          items={detail?.top_sell ?? []}
          isLoading={isLoading}
          colorVar="var(--stock-down)"
        />
      </div>
    </div>
  )
}

export default function MoneyFlowPage() {
  const { data, isLoading, isError } = useMoneyFlow()

  const foreignNet = data?.foreign?.total_net ?? 0
  const trustNet = data?.trust?.total_net ?? 0
  const dealerNet = data?.dealer?.total_net ?? 0
  const total = foreignNet + trustNet + dealerNet

  const kpiCards = [
    {
      title: '外資買賣超',
      value: isLoading ? '-' : formatVolumeValue(foreignNet),
      change: foreignNet || undefined,
      accentColor: getChangeColorVar(foreignNet),
    },
    {
      title: '投信買賣超',
      value: isLoading ? '-' : formatVolumeValue(trustNet),
      change: trustNet || undefined,
      accentColor: getChangeColorVar(trustNet),
    },
    {
      title: '自營商買賣超',
      value: isLoading ? '-' : formatVolumeValue(dealerNet),
      change: dealerNet || undefined,
      accentColor: getChangeColorVar(dealerNet),
    },
    {
      title: '三大法人合計',
      value: isLoading ? '-' : formatVolumeValue(total),
      change: total || undefined,
      accentColor: getChangeColorVar(total),
    },
  ]

  return (
    <div>
      {/* 頁面標題 */}
      <div className="mb-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold" style={{ color: 'var(--foreground)' }}>
              資金流向
            </h1>
            <p className="text-sm mt-1" style={{ color: 'var(--muted-foreground)' }}>
              三大法人買賣超分析
            </p>
          </div>
          {data?.date && (
            <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
              資料日期：{data.date}
            </span>
          )}
        </div>
      </div>

      {isError ? (
        <EmptyState
          title="無法載入資金流向資料"
          description="請確認後端服務是否正常運行，或稍後再試"
          icon="!"
        />
      ) : (
        <div className="space-y-6">
          {/* KPI 卡片 */}
          <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
            {kpiCards.map((card) => (
              <KpiCard
                key={card.title}
                isLoading={isLoading}
                accentColor={card.accentColor}
                title={card.title}
                value={card.value}
                change={card.change}
              />
            ))}
          </div>

          {/* 各法人明細 */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <InstitutionCard
              label="外資"
              detail={data?.foreign}
              isLoading={isLoading}
            />
            <InstitutionCard
              label="投信"
              detail={data?.trust}
              isLoading={isLoading}
            />
            <InstitutionCard
              label="自營商"
              detail={data?.dealer}
              isLoading={isLoading}
            />
          </div>
        </div>
      )}
    </div>
  )
}
