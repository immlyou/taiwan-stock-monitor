'use client'

import { useMemo, useState } from 'react'
import useSWR, { useSWRConfig } from 'swr'
import type { ColumnDef } from '@tanstack/react-table'
import { fetchAPI } from '@/lib/api/client'
import { DataTable } from '@/components/shared/DataTable'
import { KpiCard } from '@/components/shared/KpiCard'
import { EmptyState } from '@/components/shared/EmptyState'
import { StaleBanner } from '@/components/shared/StaleBanner'
import { formatPrice, formatPercent, getChangeColorVar } from '@/lib/utils/format'

interface Prediction {
  id: string
  code: string
  name: string
  direction: 'up' | 'down'
  targetPrice: number | null
  currentPrice: number
  targetDate: string
  createdAt: string
  status: 'pending' | 'correct' | 'wrong' | 'expired' | 'cancelled'
  actualPrice?: number
}

interface PredictionStats {
  total: number
  correct: number
  wrong: number
  pending: number
  accuracy: number
}

const SWR_KEY = '/predictions'
const STATS_KEY = '/predictions/stats'

const STATUS_LABELS: Record<string, { label: string; color: string }> = {
  pending: { label: '進行中', color: 'var(--primary)' },
  correct: { label: '預測正確', color: 'var(--stock-down)' },
  wrong: { label: '預測錯誤', color: 'var(--stock-up)' },
  expired: { label: '已過期', color: 'var(--muted-foreground)' },
  cancelled: { label: '已取消', color: 'var(--muted-foreground)' },
}

export default function PredictionsPage() {
  const { mutate } = useSWRConfig()
  const { data, isLoading, error } = useSWR<{ total: number; predictions: Prediction[] }>(SWR_KEY, fetchAPI)
  const predictions = data?.predictions
  const { data: stats, error: statsError } = useSWR<PredictionStats>(STATS_KEY, fetchAPI)

  const [dialogOpen, setDialogOpen] = useState(false)
  const [deleteId, setDeleteId] = useState<string | null>(null)
  const [form, setForm] = useState({
    code: '',
    direction: 'up' as 'up' | 'down',
    targetPrice: '',
    targetDate: '',
  })
  const [saving, setSaving] = useState(false)
  const [actionError, setActionError] = useState('')

  const handleCreate = async () => {
    if (!form.code.trim() || !form.targetPrice || !form.targetDate) return
    setSaving(true)
    setActionError('')
    try {
      await fetchAPI(SWR_KEY, {
        method: 'POST',
        body: JSON.stringify({
          code: form.code.toUpperCase(),
          direction: form.direction,
          targetPrice: Number(form.targetPrice),
          targetDate: form.targetDate,
        }),
      })
      await mutate(SWR_KEY)
      await mutate(STATS_KEY)
      setDialogOpen(false)
      setForm({ code: '', direction: 'up', targetPrice: '', targetDate: '' })
    } catch {
      setActionError('新增失敗。請確認股票代號、目標價方向與未來日期後重試。')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id: string) => {
    setSaving(true)
    setActionError('')
    try {
      await fetchAPI(`${SWR_KEY}/${id}`, { method: 'DELETE' })
      await Promise.all([mutate(SWR_KEY), mutate(STATS_KEY)])
      setDeleteId(null)
    } catch {
      setActionError('刪除失敗，記錄仍保留，請重試。')
    } finally {
      setSaving(false)
    }
  }

  const columns = useMemo<ColumnDef<Prediction, unknown>[]>(() => [
    {
      id: '代號',
      accessorKey: 'code',
      header: '代號',
      cell: ({ row }) => (
        <span className="font-medium" style={{ color: 'var(--primary)' }}>{row.original.code}</span>
      ),
    },
    {
      id: '名稱',
      accessorKey: 'name',
      header: '名稱',
      cell: ({ row }) => (
        <span style={{ color: 'var(--foreground)' }}>{row.original.name}</span>
      ),
    },
    {
      id: '方向',
      accessorKey: 'direction',
      header: '方向',
      cell: ({ row }) => {
        const d = row.original.direction
        return (
          <span
            className="font-semibold"
            style={{ color: d === 'up' ? 'var(--stock-up)' : 'var(--stock-down)' }}
          >
            {d === 'up' ? '看漲' : '看跌'}
          </span>
        )
      },
    },
    {
      id: '目標價',
      accessorKey: 'targetPrice',
      header: '目標價',
      cell: ({ row }) => (
        <span style={{ color: 'var(--foreground)' }}>{row.original.targetPrice == null ? '—' : formatPrice(row.original.targetPrice)}</span>
      ),
    },
    {
      id: '建立參考價',
      accessorKey: 'currentPrice',
      header: '建立參考價',
      cell: ({ row }) => (
        <span style={{ color: 'var(--foreground)' }}>{formatPrice(row.original.currentPrice)}</span>
      ),
    },
    {
      id: '目標價差',
      header: '目標價差',
      accessorFn: (p) => (p.currentPrice && p.targetPrice != null ? ((p.targetPrice - p.currentPrice) / p.currentPrice) * 100 : 0),
      cell: ({ getValue }) => {
        const gapPct = getValue() as number
        return (
          <span className="font-semibold" style={{ color: getChangeColorVar(gapPct) }}>
            {formatPercent(gapPct, 2, true)}
          </span>
        )
      },
    },
    {
      id: '目標日期',
      accessorKey: 'targetDate',
      header: '目標日期',
      cell: ({ row }) => (
        <span style={{ color: 'var(--foreground)' }}>{row.original.targetDate}</span>
      ),
    },
    {
      id: '建立日期',
      header: '建立日期',
      accessorFn: (p) => p.createdAt.slice(0, 10),
      cell: ({ getValue }) => (
        <span style={{ color: 'var(--muted-foreground)' }}>{getValue() as string}</span>
      ),
    },
    {
      id: '狀態',
      accessorKey: 'status',
      header: '狀態',
      cell: ({ row }) => {
        const st = STATUS_LABELS[row.original.status] ?? { label: row.original.status, color: 'var(--foreground)' }
        return (
          <span
            className="px-2 py-0.5 rounded-full text-xs font-medium"
            style={{ background: st.color + '22', color: st.color }}
          >
            {st.label}
          </span>
        )
      },
    },
    {
      id: '實際價',
      header: '實際價',
      accessorFn: (p) => (p.actualPrice != null ? formatPrice(p.actualPrice) : '—'),
      cell: ({ getValue }) => (
        <span style={{ color: 'var(--muted-foreground)' }}>{getValue() as string}</span>
      ),
    },
    {
      id: '操作',
      header: '操作',
      enableSorting: false,
      cell: ({ row }) => (
        <button
          onClick={() => setDeleteId(row.original.id)}
          className="text-xs px-2 py-1 rounded"
          style={{ color: 'var(--destructive)' }}
        >
          刪除
        </button>
      ),
    },
  ], [])

  return (
    <div>
      <div className="mb-6 flex justify-between items-start">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: 'var(--foreground)' }}>預測驗證</h1>
          <p className="text-sm mt-1" style={{ color: 'var(--muted-foreground)' }}>以建立後至截止日的每日收盤價驗證目標價；不包含盤中觸價。參考價為建立時可取得的最新收盤。</p>
        </div>
        <button
          onClick={() => { setActionError(''); setDialogOpen(true) }}
          className="h-9 px-4 rounded-md text-sm font-medium"
          style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}
        >
          新增預測
        </button>
      </div>

      {/* 統計卡片 */}
      {statsError && stats && <StaleBanner />}
      {statsError && !stats ? (
        <div className="mb-6">
          <EmptyState
            title="無法載入統計資料"
            description="請確認後端服務是否正常運行，或稍後再試"
            icon="!"
          />
        </div>
      ) : stats && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
          {[
            { title: '總預測數', value: String(stats.total), accentColor: 'var(--primary)' },
            { title: '正確次數', value: String(stats.correct), accentColor: 'var(--stock-down)' },
            { title: '錯誤次數', value: String(stats.wrong), accentColor: 'var(--stock-up)' },
            { title: '進行中', value: String(stats.pending), accentColor: 'var(--primary)' },
            { title: '準確率', value: formatPercent(stats.accuracy, 1).replace('+', ''), accentColor: stats.accuracy >= 60 ? 'var(--stock-down)' : 'var(--stock-up)' },
          ].map(({ title, value, accentColor }) => (
            <KpiCard key={title} title={title} value={value} accentColor={accentColor} />
          ))}
        </div>
      )}

      {/* 預測列表 */}
      {error && predictions && <StaleBanner />}
      {isLoading ? (
        <div className="space-y-2">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-16 rounded-lg animate-pulse" style={{ background: 'var(--card)' }} />
          ))}
        </div>
      ) : error && !predictions ? (
        <div
          className="rounded-lg"
          style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
        >
          <EmptyState
            title="無法載入預測記錄"
            description="請確認後端服務是否正常運行，或稍後再試"
            icon="!"
          />
        </div>
      ) : predictions && predictions.length > 0 ? (
        <DataTable
          columns={columns}
          data={predictions}
          searchable
          searchPlaceholder="搜尋代號 / 名稱..."
          exportable
          exportFilename="predictions"
          pageSize={20}
        />
      ) : (
        <div
          className="rounded-lg p-12 text-center"
          style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
        >
          <p style={{ color: 'var(--muted-foreground)' }}>尚無預測記錄，點擊新增預測開始追蹤</p>
        </div>
      )}

      {/* 新增 Dialog */}
      {dialogOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: 'rgba(0,0,0,0.7)' }}>
          <div
            className="w-full max-w-md rounded-lg p-6"
            style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
          >
            <h2 className="text-lg font-semibold mb-4" style={{ color: 'var(--foreground)' }}>新增預測</h2>
            <div className="space-y-3">
              <div>
                <label className="block text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>股票代號</label>
                <input
                  aria-label="股票代號"
                  type="text"
                  value={form.code}
                  onChange={(e) => setForm(p => ({ ...p, code: e.target.value.toUpperCase() }))}
                  placeholder="例：2330"
                  className="h-9 w-full rounded-md border px-3 text-sm"
                  style={{ background: 'var(--background)', border: '1px solid var(--border)', color: 'var(--foreground)' }}
                />
              </div>
              <div>
                <label className="block text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>方向</label>
                <div className="flex gap-2">
                  {(['up', 'down'] as const).map((d) => (
                    <button
                      key={d}
                      onClick={() => setForm(p => ({ ...p, direction: d }))}
                      className="flex-1 h-9 rounded-md text-sm font-medium"
                      style={{
                        background: form.direction === d
                          ? (d === 'up' ? 'var(--stock-up)' : 'var(--stock-down)')
                          : 'var(--secondary)',
                        color: form.direction === d ? '#fff' : 'var(--foreground)',
                      }}
                    >
                      {d === 'up' ? '看漲' : '看跌'}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <label className="block text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>目標價</label>
                <input
                  aria-label="目標價"
                  min="0.01"
                  step="any"
                  type="number"
                  value={form.targetPrice}
                  onChange={(e) => setForm(p => ({ ...p, targetPrice: e.target.value }))}
                  placeholder="例：600"
                  className="h-9 w-full rounded-md border px-3 text-sm"
                  style={{ background: 'var(--background)', border: '1px solid var(--border)', color: 'var(--foreground)' }}
                />
              </div>
              <div>
                <label className="block text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>目標日期</label>
                <input
                  aria-label="目標日期"
                  type="date"
                  value={form.targetDate}
                  onChange={(e) => setForm(p => ({ ...p, targetDate: e.target.value }))}
                  className="h-9 w-full rounded-md border px-3 text-sm"
                  style={{ background: 'var(--background)', border: '1px solid var(--border)', color: 'var(--foreground)' }}
                />
              </div>
            </div>
            {actionError && <p role="alert" className="mt-3 text-sm" style={{ color: 'var(--destructive)' }}>{actionError}</p>}
            <div className="mt-4 flex justify-end gap-2">
              <button
                onClick={() => setDialogOpen(false)}
                className="h-9 px-4 rounded-md text-sm font-medium"
                style={{ background: 'var(--secondary)', color: 'var(--foreground)' }}
              >
                取消
              </button>
              <button
                onClick={handleCreate}
                disabled={saving}
                className="h-9 px-4 rounded-md text-sm font-medium disabled:opacity-60"
                style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}
              >
                {saving ? '儲存中...' : '新增'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 刪除確認 */}
      {deleteId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: 'rgba(0,0,0,0.7)' }}>
          <div
            className="w-full max-w-sm rounded-lg p-6"
            style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
          >
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--foreground)' }}>確認刪除</h2>
            <p className="text-sm mb-4" style={{ color: 'var(--muted-foreground)' }}>確定要刪除此預測記錄嗎？</p>
            {actionError && <p role="alert" style={{ color: 'var(--destructive)' }}>{actionError}</p>}
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setDeleteId(null)}
                className="h-9 px-4 rounded-md text-sm"
                style={{ background: 'var(--secondary)', color: 'var(--foreground)' }}
              >
                取消
              </button>
              <button
                onClick={() => handleDelete(deleteId)}
                disabled={saving}
                className="h-9 px-4 rounded-md text-sm"
                style={{ background: 'var(--destructive)', color: 'var(--destructive-foreground)' }}
              >
                刪除
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
