'use client'

import { useState } from 'react'
import useSWR, { mutate } from 'swr'
import { fetchAPI } from '@/lib/api/client'

interface Prediction {
  id: string
  code: string
  name: string
  direction: 'up' | 'down'
  targetPrice: number
  currentPrice: number
  targetDate: string
  createdAt: string
  status: 'pending' | 'correct' | 'wrong' | 'expired'
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
}

export default function PredictionsPage() {
  const { data: predictions, isLoading } = useSWR<Prediction[]>(SWR_KEY, fetchAPI)
  const { data: stats } = useSWR<PredictionStats>(STATS_KEY, fetchAPI)

  const [dialogOpen, setDialogOpen] = useState(false)
  const [deleteId, setDeleteId] = useState<string | null>(null)
  const [form, setForm] = useState({
    code: '',
    direction: 'up' as 'up' | 'down',
    targetPrice: '',
    targetDate: '',
  })
  const [saving, setSaving] = useState(false)

  const handleCreate = async () => {
    if (!form.code.trim() || !form.targetPrice || !form.targetDate) return
    setSaving(true)
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
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id: string) => {
    await fetchAPI(`${SWR_KEY}/${id}`, { method: 'DELETE' })
    await mutate(SWR_KEY)
    await mutate(STATS_KEY)
    setDeleteId(null)
  }

  return (
    <div>
      <div className="mb-6 flex justify-between items-start">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: 'var(--foreground)' }}>預測驗證</h1>
          <p className="text-sm mt-1" style={{ color: 'var(--muted-foreground)' }}>股價預測記錄與準確率追蹤</p>
        </div>
        <button
          onClick={() => setDialogOpen(true)}
          className="h-9 px-4 rounded-md text-sm font-medium"
          style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}
        >
          新增預測
        </button>
      </div>

      {/* 統計卡片 */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
          {[
            { label: '總預測數', value: stats.total },
            { label: '正確次數', value: stats.correct, color: 'var(--stock-down)' },
            { label: '錯誤次數', value: stats.wrong, color: 'var(--stock-up)' },
            { label: '進行中', value: stats.pending, color: 'var(--primary)' },
            { label: '準確率', value: `${stats.accuracy.toFixed(1)}%`, color: stats.accuracy >= 60 ? 'var(--stock-down)' : 'var(--stock-up)' },
          ].map(({ label, value, color }) => (
            <div
              key={label}
              className="rounded-lg p-4"
              style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
            >
              <p className="text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>{label}</p>
              <p className="text-2xl font-bold tabular-nums" style={{ color: color ?? 'var(--foreground)' }}>
                {value}
              </p>
            </div>
          ))}
        </div>
      )}

      {/* 預測列表 */}
      {isLoading ? (
        <div className="space-y-2">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-16 rounded-lg animate-pulse" style={{ background: 'var(--card)' }} />
          ))}
        </div>
      ) : predictions && predictions.length > 0 ? (
        <div
          className="rounded-lg overflow-hidden"
          style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
        >
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ background: 'var(--secondary)' }}>
                  {['代號', '名稱', '方向', '目標價', '現價', '目標日期', '建立日期', '狀態', '實際價', '操作'].map(h => (
                    <th key={h} className="text-left py-2 px-4" style={{ color: 'var(--muted-foreground)' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {predictions.map((p) => {
                  const st = STATUS_LABELS[p.status] ?? { label: p.status, color: 'var(--foreground)' }
                  return (
                    <tr key={p.id} style={{ borderBottom: '1px solid var(--border)' }}>
                      <td className="py-2 px-4 font-medium" style={{ color: 'var(--primary)' }}>{p.code}</td>
                      <td className="py-2 px-4" style={{ color: 'var(--foreground)' }}>{p.name}</td>
                      <td
                        className="py-2 px-4 font-semibold"
                        style={{ color: p.direction === 'up' ? 'var(--stock-up)' : 'var(--stock-down)' }}
                      >
                        {p.direction === 'up' ? '看漲' : '看跌'}
                      </td>
                      <td className="py-2 px-4 tabular-nums" style={{ color: 'var(--foreground)' }}>
                        {p.targetPrice.toFixed(2)}
                      </td>
                      <td className="py-2 px-4 tabular-nums" style={{ color: 'var(--foreground)' }}>
                        {p.currentPrice.toFixed(2)}
                      </td>
                      <td className="py-2 px-4" style={{ color: 'var(--foreground)' }}>{p.targetDate}</td>
                      <td className="py-2 px-4" style={{ color: 'var(--muted-foreground)' }}>{p.createdAt.slice(0, 10)}</td>
                      <td className="py-2 px-4">
                        <span
                          className="px-2 py-0.5 rounded-full text-xs font-medium"
                          style={{ background: st.color + '22', color: st.color }}
                        >
                          {st.label}
                        </span>
                      </td>
                      <td className="py-2 px-4 tabular-nums" style={{ color: 'var(--muted-foreground)' }}>
                        {p.actualPrice != null ? p.actualPrice.toFixed(2) : '—'}
                      </td>
                      <td className="py-2 px-4">
                        <button
                          onClick={() => setDeleteId(p.id)}
                          className="text-xs px-2 py-1 rounded"
                          style={{ color: 'var(--destructive)' }}
                        >
                          刪除
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
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
                  type="date"
                  value={form.targetDate}
                  onChange={(e) => setForm(p => ({ ...p, targetDate: e.target.value }))}
                  className="h-9 w-full rounded-md border px-3 text-sm"
                  style={{ background: 'var(--background)', border: '1px solid var(--border)', color: 'var(--foreground)' }}
                />
              </div>
            </div>
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
