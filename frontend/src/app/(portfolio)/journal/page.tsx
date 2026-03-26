'use client'

import { useState } from 'react'
import useSWR, { mutate } from 'swr'
import { fetchAPI } from '@/lib/api/client'
import { getChangeColorVar } from '@/lib/utils/format'

interface JournalEntry {
  id: string
  date: string
  code: string
  name: string
  action: 'buy' | 'sell' | 'add' | 'reduce'
  shares: number
  price: number
  totalAmount: number
  fee: number
  note?: string
  realizedPnl?: number
  createdAt: string
}

interface JournalResponse {
  entries: JournalEntry[]
  total: number
  page: number
  pageSize: number
}

const SWR_KEY_BASE = '/journal'

const ACTION_LABELS: Record<string, { label: string; color: string }> = {
  buy: { label: '買入', color: 'var(--stock-up)' },
  sell: { label: '賣出', color: 'var(--stock-down)' },
  add: { label: '加碼', color: 'var(--stock-up)' },
  reduce: { label: '減碼', color: 'var(--stock-down)' },
}

export default function JournalPage() {
  const [page, setPage] = useState(1)
  const PAGE_SIZE = 20
  const [dialogOpen, setDialogOpen] = useState(false)
  const [deleteId, setDeleteId] = useState<string | null>(null)
  const [form, setForm] = useState({
    date: new Date().toISOString().slice(0, 10),
    code: '',
    action: 'buy' as JournalEntry['action'],
    shares: '',
    price: '',
    note: '',
  })
  const [saving, setSaving] = useState(false)

  const swrKey = `${SWR_KEY_BASE}?page=${page}&pageSize=${PAGE_SIZE}`
  const { data, isLoading, error } = useSWR<JournalResponse>(swrKey, fetchAPI)

  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 1

  const handleCreate = async () => {
    if (!form.code.trim() || !form.shares || !form.price) return
    setSaving(true)
    try {
      await fetchAPI(SWR_KEY_BASE, {
        method: 'POST',
        body: JSON.stringify({
          date: form.date,
          code: form.code.toUpperCase(),
          action: form.action,
          shares: Number(form.shares),
          price: Number(form.price),
          note: form.note || undefined,
        }),
      })
      await mutate(swrKey)
      setDialogOpen(false)
      setForm({ date: new Date().toISOString().slice(0, 10), code: '', action: 'buy', shares: '', price: '', note: '' })
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id: string) => {
    await fetchAPI(`${SWR_KEY_BASE}/${id}`, { method: 'DELETE' })
    await mutate(swrKey)
    setDeleteId(null)
  }

  const totalAmount = form.shares && form.price
    ? (Number(form.shares) * 1000 * Number(form.price)).toLocaleString()
    : '—'

  return (
    <div>
      <div className="mb-6 flex justify-between items-start">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: 'var(--foreground)' }}>交易日誌</h1>
          <p className="text-sm mt-1" style={{ color: 'var(--muted-foreground)' }}>買賣交易記錄管理</p>
        </div>
        <button
          onClick={() => setDialogOpen(true)}
          className="h-9 px-4 rounded-md text-sm font-medium"
          style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}
        >
          新增交易
        </button>
      </div>

      {error ? (
        <div className="rounded-lg p-6 text-center" style={{ background: 'var(--card)', border: '1px solid var(--border)' }}>
          <p style={{ color: 'var(--destructive)' }}>資料載入失敗</p>
        </div>
      ) : isLoading ? (
        <div className="space-y-2">
          {[...Array(10)].map((_, i) => (
            <div key={i} className="h-12 rounded animate-pulse" style={{ background: 'var(--card)' }} />
          ))}
        </div>
      ) : (
        <>
          <div
            className="rounded-lg overflow-hidden mb-4"
            style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
          >
            {data && data.entries.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr style={{ background: 'var(--secondary)' }}>
                      {['日期', '代號', '名稱', '操作', '張數', '成交價', '成交金額', '手續費', '已實現損益', '備注', '操作'].map(h => (
                        <th key={h} className="text-left py-2 px-4" style={{ color: 'var(--muted-foreground)', whiteSpace: 'nowrap' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {data.entries.map((e) => {
                      const actionInfo = ACTION_LABELS[e.action] ?? { label: e.action, color: 'var(--foreground)' }
                      return (
                        <tr key={e.id} style={{ borderBottom: '1px solid var(--border)' }}>
                          <td className="py-2 px-4 tabular-nums" style={{ color: 'var(--muted-foreground)', whiteSpace: 'nowrap' }}>{e.date}</td>
                          <td className="py-2 px-4 font-medium" style={{ color: 'var(--primary)' }}>{e.code}</td>
                          <td className="py-2 px-4" style={{ color: 'var(--foreground)' }}>{e.name}</td>
                          <td className="py-2 px-4 font-semibold" style={{ color: actionInfo.color }}>{actionInfo.label}</td>
                          <td className="py-2 px-4 tabular-nums" style={{ color: 'var(--foreground)' }}>{e.shares}</td>
                          <td className="py-2 px-4 tabular-nums" style={{ color: 'var(--foreground)' }}>{e.price.toFixed(2)}</td>
                          <td className="py-2 px-4 tabular-nums" style={{ color: 'var(--foreground)' }}>
                            {(e.totalAmount / 1e4).toFixed(1)} 萬
                          </td>
                          <td className="py-2 px-4 tabular-nums" style={{ color: 'var(--muted-foreground)' }}>
                            {e.fee.toLocaleString()}
                          </td>
                          <td
                            className="py-2 px-4 tabular-nums font-medium"
                            style={{ color: e.realizedPnl != null ? getChangeColorVar(e.realizedPnl) : 'var(--muted-foreground)' }}
                          >
                            {e.realizedPnl != null
                              ? `${e.realizedPnl > 0 ? '+' : ''}${(e.realizedPnl / 1e4).toFixed(1)} 萬`
                              : '—'}
                          </td>
                          <td className="py-2 px-4 max-w-32 truncate" style={{ color: 'var(--muted-foreground)' }}>
                            {e.note ?? '—'}
                          </td>
                          <td className="py-2 px-4">
                            <button
                              onClick={() => setDeleteId(e.id)}
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
            ) : (
              <div className="p-12 text-center">
                <p style={{ color: 'var(--muted-foreground)' }}>尚無交易記錄</p>
              </div>
            )}
          </div>

          {/* 分頁 */}
          {totalPages > 1 && (
            <div className="flex justify-center gap-2">
              <button
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
                className="h-8 px-3 rounded text-sm disabled:opacity-50"
                style={{ background: 'var(--secondary)', color: 'var(--foreground)' }}
              >
                上一頁
              </button>
              <span className="h-8 flex items-center px-3 text-sm" style={{ color: 'var(--muted-foreground)' }}>
                {page} / {totalPages}
              </span>
              <button
                onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="h-8 px-3 rounded text-sm disabled:opacity-50"
                style={{ background: 'var(--secondary)', color: 'var(--foreground)' }}
              >
                下一頁
              </button>
            </div>
          )}
        </>
      )}

      {/* 新增 Dialog */}
      {dialogOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: 'rgba(0,0,0,0.7)' }}>
          <div
            className="w-full max-w-md rounded-lg p-6"
            style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
          >
            <h2 className="text-lg font-semibold mb-4" style={{ color: 'var(--foreground)' }}>新增交易記錄</h2>
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>交易日期</label>
                  <input
                    type="date"
                    value={form.date}
                    onChange={(e) => setForm(p => ({ ...p, date: e.target.value }))}
                    className="h-9 w-full rounded-md border px-3 text-sm"
                    style={{ background: 'var(--background)', border: '1px solid var(--border)', color: 'var(--foreground)' }}
                  />
                </div>
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
              </div>

              <div>
                <label className="block text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>操作類型</label>
                <div className="grid grid-cols-4 gap-1">
                  {(['buy', 'sell', 'add', 'reduce'] as const).map((a) => {
                    const info = ACTION_LABELS[a]
                    return (
                      <button
                        key={a}
                        onClick={() => setForm(p => ({ ...p, action: a }))}
                        className="h-9 rounded-md text-sm font-medium"
                        style={{
                          background: form.action === a ? info.color : 'var(--secondary)',
                          color: form.action === a ? '#fff' : 'var(--foreground)',
                        }}
                      >
                        {info.label}
                      </button>
                    )
                  })}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>張數</label>
                  <input
                    type="number"
                    value={form.shares}
                    onChange={(e) => setForm(p => ({ ...p, shares: e.target.value }))}
                    placeholder="例：5"
                    className="h-9 w-full rounded-md border px-3 text-sm"
                    style={{ background: 'var(--background)', border: '1px solid var(--border)', color: 'var(--foreground)' }}
                  />
                </div>
                <div>
                  <label className="block text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>成交價（元/股）</label>
                  <input
                    type="number"
                    value={form.price}
                    onChange={(e) => setForm(p => ({ ...p, price: e.target.value }))}
                    placeholder="例：580"
                    className="h-9 w-full rounded-md border px-3 text-sm"
                    style={{ background: 'var(--background)', border: '1px solid var(--border)', color: 'var(--foreground)' }}
                  />
                </div>
              </div>

              <div className="rounded-md p-3" style={{ background: 'var(--secondary)' }}>
                <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>預估金額：</span>
                <span className="text-sm font-semibold ml-1" style={{ color: 'var(--foreground)' }}>
                  {totalAmount} 元
                </span>
              </div>

              <div>
                <label className="block text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>備注（選填）</label>
                <input
                  type="text"
                  value={form.note}
                  onChange={(e) => setForm(p => ({ ...p, note: e.target.value }))}
                  placeholder="交易理由或備注"
                  className="h-9 w-full rounded-md border px-3 text-sm"
                  style={{ background: 'var(--background)', border: '1px solid var(--border)', color: 'var(--foreground)' }}
                />
              </div>
            </div>
            <div className="mt-4 flex justify-end gap-2">
              <button
                onClick={() => setDialogOpen(false)}
                className="h-9 px-4 rounded-md text-sm"
                style={{ background: 'var(--secondary)', color: 'var(--foreground)' }}
              >
                取消
              </button>
              <button
                onClick={handleCreate}
                disabled={saving}
                className="h-9 px-4 rounded-md text-sm disabled:opacity-60"
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
          <div className="w-full max-w-sm rounded-lg p-6" style={{ background: 'var(--card)', border: '1px solid var(--border)' }}>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--foreground)' }}>確認刪除</h2>
            <p className="text-sm mb-4" style={{ color: 'var(--muted-foreground)' }}>確定要刪除此交易記錄嗎？</p>
            <div className="flex justify-end gap-2">
              <button onClick={() => setDeleteId(null)} className="h-9 px-4 rounded-md text-sm" style={{ background: 'var(--secondary)', color: 'var(--foreground)' }}>取消</button>
              <button onClick={() => handleDelete(deleteId)} className="h-9 px-4 rounded-md text-sm" style={{ background: 'var(--destructive)', color: 'var(--destructive-foreground)' }}>刪除</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
