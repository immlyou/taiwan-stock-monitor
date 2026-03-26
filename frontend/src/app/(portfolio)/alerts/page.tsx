'use client'

import { useState } from 'react'
import useSWR, { mutate } from 'swr'
import { fetchAPI } from '@/lib/api/client'
import { Alert } from '@/lib/types'

const SWR_KEY = '/alerts'

const ALERT_TYPES: { key: Alert['type']; label: string; unit: string }[] = [
  { key: 'price_above', label: '價格高於', unit: '元' },
  { key: 'price_below', label: '價格低於', unit: '元' },
  { key: 'change_percent', label: '漲跌幅超過', unit: '%' },
  { key: 'volume', label: '成交量超過', unit: '張' },
]

export default function AlertsPage() {
  const { data: alerts, isLoading, error } = useSWR<Alert[]>(SWR_KEY, fetchAPI)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [deleteId, setDeleteId] = useState<string | null>(null)
  const [form, setForm] = useState({
    code: '',
    type: 'price_above' as Alert['type'],
    value: '',
  })
  const [saving, setSaving] = useState(false)

  const handleCreate = async () => {
    if (!form.code.trim() || !form.value) return
    setSaving(true)
    try {
      await fetchAPI(SWR_KEY, {
        method: 'POST',
        body: JSON.stringify({
          code: form.code.toUpperCase(),
          type: form.type,
          value: Number(form.value),
          enabled: true,
        }),
      })
      await mutate(SWR_KEY)
      setDialogOpen(false)
      setForm({ code: '', type: 'price_above', value: '' })
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id: string) => {
    await fetchAPI(`${SWR_KEY}/${id}`, { method: 'DELETE' })
    await mutate(SWR_KEY)
    setDeleteId(null)
  }

  const handleToggle = async (alert: Alert) => {
    await fetchAPI(`${SWR_KEY}/${alert.id}`, {
      method: 'PATCH',
      body: JSON.stringify({ enabled: !alert.enabled }),
    })
    await mutate(SWR_KEY)
  }

  const activeCount = alerts?.filter(a => a.enabled && !a.triggered).length ?? 0
  const triggeredCount = alerts?.filter(a => a.triggered).length ?? 0

  return (
    <div>
      <div className="mb-6 flex justify-between items-start">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: 'var(--foreground)' }}>警報設定</h1>
          <p className="text-sm mt-1" style={{ color: 'var(--muted-foreground)' }}>股價條件警報管理</p>
        </div>
        <button
          onClick={() => setDialogOpen(true)}
          className="h-9 px-4 rounded-md text-sm font-medium"
          style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}
        >
          新增警報
        </button>
      </div>

      {/* 統計 */}
      {alerts && (
        <div className="grid grid-cols-3 gap-3 mb-6">
          <div className="rounded-lg p-4" style={{ background: 'var(--card)', border: '1px solid var(--border)' }}>
            <p className="text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>總警報數</p>
            <p className="text-2xl font-bold" style={{ color: 'var(--foreground)' }}>{alerts.length}</p>
          </div>
          <div className="rounded-lg p-4" style={{ background: 'var(--card)', border: '1px solid var(--border)' }}>
            <p className="text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>監控中</p>
            <p className="text-2xl font-bold" style={{ color: 'var(--primary)' }}>{activeCount}</p>
          </div>
          <div className="rounded-lg p-4" style={{ background: 'var(--card)', border: '1px solid var(--border)' }}>
            <p className="text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>已觸發</p>
            <p className="text-2xl font-bold" style={{ color: 'var(--destructive)' }}>{triggeredCount}</p>
          </div>
        </div>
      )}

      {/* 警報列表 */}
      {error ? (
        <div className="rounded-lg p-6 text-center" style={{ background: 'var(--card)', border: '1px solid var(--border)' }}>
          <p style={{ color: 'var(--destructive)' }}>資料載入失敗</p>
        </div>
      ) : isLoading ? (
        <div className="space-y-2">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-16 rounded-lg animate-pulse" style={{ background: 'var(--card)' }} />
          ))}
        </div>
      ) : alerts && alerts.length > 0 ? (
        <div className="space-y-2">
          {alerts.map((alert) => {
            const typeInfo = ALERT_TYPES.find(t => t.key === alert.type)
            const statusColor = alert.triggered
              ? 'var(--destructive)'
              : alert.enabled
              ? 'var(--stock-down)'
              : 'var(--muted-foreground)'
            const statusLabel = alert.triggered ? '已觸發' : alert.enabled ? '監控中' : '已停用'

            return (
              <div
                key={alert.id}
                className="rounded-lg p-4 flex items-center gap-4"
                style={{
                  background: 'var(--card)',
                  border: `1px solid ${alert.triggered ? 'var(--destructive)' : 'var(--border)'}`,
                }}
              >
                {/* 開關 */}
                <button
                  onClick={() => handleToggle(alert)}
                  disabled={alert.triggered}
                  className="relative w-10 h-5 rounded-full transition-colors disabled:opacity-50 flex-shrink-0"
                  style={{
                    background: alert.enabled ? 'var(--primary)' : 'var(--secondary)',
                  }}
                >
                  <span
                    className="absolute top-0.5 w-4 h-4 rounded-full bg-white transition-all"
                    style={{ left: alert.enabled ? '22px' : '2px' }}
                  />
                </button>

                {/* 代號 */}
                <div className="flex-shrink-0">
                  <p className="font-semibold" style={{ color: 'var(--primary)' }}>{alert.code}</p>
                  <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>{alert.name}</p>
                </div>

                {/* 條件 */}
                <div className="flex-1">
                  <p className="text-sm" style={{ color: 'var(--foreground)' }}>
                    {typeInfo?.label ?? alert.type}
                    <span className="font-semibold ml-1">
                      {alert.value} {typeInfo?.unit}
                    </span>
                  </p>
                  <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
                    建立於 {alert.createdAt.slice(0, 10)}
                  </p>
                </div>

                {/* 狀態 */}
                <span
                  className="px-2 py-1 rounded-full text-xs font-medium flex-shrink-0"
                  style={{ background: statusColor + '22', color: statusColor }}
                >
                  {statusLabel}
                </span>

                {/* 刪除 */}
                <button
                  onClick={() => setDeleteId(alert.id)}
                  className="text-xs px-2 py-1 rounded flex-shrink-0"
                  style={{ color: 'var(--destructive)' }}
                >
                  刪除
                </button>
              </div>
            )
          })}
        </div>
      ) : (
        <div
          className="rounded-lg p-12 text-center"
          style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
        >
          <p className="text-lg mb-2" style={{ color: 'var(--muted-foreground)' }}>尚無警報設定</p>
          <p className="text-sm" style={{ color: 'var(--muted-foreground)' }}>
            點擊新增警報，設定股價觸發條件
          </p>
        </div>
      )}

      {/* 新增 Dialog */}
      {dialogOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: 'rgba(0,0,0,0.7)' }}>
          <div
            className="w-full max-w-md rounded-lg p-6"
            style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
          >
            <h2 className="text-lg font-semibold mb-4" style={{ color: 'var(--foreground)' }}>新增警報</h2>
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
                <label className="block text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>警報類型</label>
                <select
                  value={form.type}
                  onChange={(e) => setForm(p => ({ ...p, type: e.target.value as Alert['type'] }))}
                  className="h-9 w-full rounded-md border px-3 text-sm"
                  style={{ background: 'var(--background)', border: '1px solid var(--border)', color: 'var(--foreground)' }}
                >
                  {ALERT_TYPES.map(t => (
                    <option key={t.key} value={t.key}>{t.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>
                  觸發值（{ALERT_TYPES.find(t => t.key === form.type)?.unit}）
                </label>
                <input
                  type="number"
                  value={form.value}
                  onChange={(e) => setForm(p => ({ ...p, value: e.target.value }))}
                  placeholder="例：600"
                  className="h-9 w-full rounded-md border px-3 text-sm"
                  style={{ background: 'var(--background)', border: '1px solid var(--border)', color: 'var(--foreground)' }}
                />
              </div>
              <div
                className="rounded-md p-3 text-sm"
                style={{ background: 'var(--secondary)', color: 'var(--muted-foreground)' }}
              >
                當 <span className="font-semibold" style={{ color: 'var(--foreground)' }}>{form.code || '[股票]'}</span>
                {' '}{ALERT_TYPES.find(t => t.key === form.type)?.label}
                {' '}<span className="font-semibold" style={{ color: 'var(--foreground)' }}>
                  {form.value || '[值]'} {ALERT_TYPES.find(t => t.key === form.type)?.unit}
                </span>
                {' '}時觸發警報
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
            <p className="text-sm mb-4" style={{ color: 'var(--muted-foreground)' }}>確定要刪除此警報嗎？</p>
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
