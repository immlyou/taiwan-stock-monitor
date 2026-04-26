'use client'

import { useState } from 'react'
import useSWR, { mutate } from 'swr'
import { fetchAPI } from '@/lib/api/client'
import { Alert } from '@/lib/types'

const SWR_KEY = '/alerts'

// API 回傳 { total, alerts: [...] }
interface AlertsResponse {
  total: number
  alerts: Alert[]
}

interface AlertTypeOption {
  type: Alert['type']
  label: string
  unit: string
  default_value: number
}

interface AlertTypesResponse {
  types: AlertTypeOption[]
}

interface SmartAlert {
  stock_id: string
  name?: string
  severity: 'high' | 'medium' | string
  latest_price: number
  change_pct: number
  score?: number | null
  reasons: string[]
}

interface SmartAlertsResponse {
  total: number
  alerts: SmartAlert[]
}

const FALLBACK_ALERT_TYPES: AlertTypeOption[] = [
  { type: 'price_above', label: '價格高於', unit: '元', default_value: 600 },
  { type: 'price_below', label: '價格低於', unit: '元', default_value: 500 },
  { type: 'rsi_above', label: 'RSI 高於', unit: '', default_value: 70 },
  { type: 'rsi_below', label: 'RSI 低於', unit: '', default_value: 30 },
  { type: 'volume_spike', label: '爆量倍數', unit: '倍', default_value: 2 },
  { type: 'new_high', label: '創 N 日新高', unit: '日', default_value: 20 },
  { type: 'new_low', label: '創 N 日新低', unit: '日', default_value: 20 },
]

export default function AlertsPage() {
  const { data: alertsData, isLoading, error } = useSWR<AlertsResponse>(SWR_KEY, fetchAPI)
  const { data: typesData } = useSWR<AlertTypesResponse>('/alerts/types', fetchAPI)
  const { data: smartData } = useSWR<SmartAlertsResponse>('/alerts/smart-preview?top_n=8', fetchAPI)
  const alerts = alertsData?.alerts
  const alertTypes = typesData?.types ?? FALLBACK_ALERT_TYPES
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
          stock_id: form.code.toUpperCase(),
          type: form.type,
          value: Number(form.value),
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

      {smartData?.alerts?.length ? (
        <div
          className="rounded-lg p-4 mb-6"
          style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
        >
          <div className="flex items-center justify-between mb-3">
            <div>
              <h2 className="text-sm font-semibold" style={{ color: 'var(--foreground)' }}>智慧警報建議</h2>
              <p className="text-xs mt-0.5" style={{ color: 'var(--muted-foreground)' }}>
                量化評分、突破、跌破與爆量訊號
              </p>
            </div>
            <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>{smartData.total} 筆</span>
          </div>
          <div className="grid md:grid-cols-2 gap-2">
            {smartData.alerts.map((item) => (
              <div key={`${item.stock_id}-${item.reasons.join(',')}`} className="rounded-md p-3" style={{ background: 'var(--secondary)' }}>
                <div className="flex items-center justify-between gap-2 mb-1">
                  <p className="font-semibold text-sm" style={{ color: 'var(--primary)' }}>
                    {item.stock_id} {item.name ?? ''}
                  </p>
                  <span className="text-xs" style={{ color: item.severity === 'high' ? 'var(--destructive)' : 'var(--muted-foreground)' }}>
                    {item.severity === 'high' ? '高' : '中'}
                  </span>
                </div>
                <p className="text-xs mb-2" style={{ color: 'var(--muted-foreground)' }}>
                  現價 {item.latest_price.toFixed(2)} / 評分 {item.score?.toFixed(1) ?? '—'}
                </p>
                <p className="text-xs" style={{ color: 'var(--foreground)' }}>{item.reasons[0]}</p>
              </div>
            ))}
          </div>
        </div>
      ) : null}

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
            const typeInfo = alertTypes.find(t => t.type === alert.type)
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
                  <p className="font-semibold" style={{ color: 'var(--primary)' }}>{alert.stock_id ?? alert.code}</p>
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
                    建立於 {(alert.created_at ?? alert.createdAt ?? '').slice(0, 10)}
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
                  {alertTypes.map(t => (
                    <option key={t.type} value={t.type}>{t.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>
                  觸發值（{alertTypes.find(t => t.type === form.type)?.unit}）
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
                {' '}{alertTypes.find(t => t.type === form.type)?.label}
                {' '}<span className="font-semibold" style={{ color: 'var(--foreground)' }}>
                  {form.value || '[值]'} {alertTypes.find(t => t.type === form.type)?.unit}
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
