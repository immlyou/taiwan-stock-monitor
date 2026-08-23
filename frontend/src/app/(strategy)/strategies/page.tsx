'use client'

import { useState } from 'react'
import useSWR, { useSWRConfig } from 'swr'
import { fetchAPI } from '@/lib/api/client'
import { Strategy, StrategyCondition } from '@/lib/types'

const FIELDS = [
  { key: 'pe', label: 'PE 本益比' },
  { key: 'pb', label: 'PB 股價淨值比' },
  { key: 'roe', label: 'ROE %' },
  { key: 'dividend_yield', label: '殖利率 %' },
  { key: 'change_percent', label: '漲跌幅 %' },
  { key: 'volume', label: '成交量（張）' },
  { key: 'rsi14', label: 'RSI(14)' },
  { key: 'ma20', label: 'MA20' },
]

const OPERATORS: { key: StrategyCondition['operator']; label: string }[] = [
  { key: 'gt', label: '>' },
  { key: 'gte', label: '>=' },
  { key: 'lt', label: '<' },
  { key: 'lte', label: '<=' },
  { key: 'eq', label: '=' },
]

const SWR_KEY = '/strategies/saved'

interface SavedStrategiesResponse {
  total: number
  strategies: Strategy[]
}

interface DialogState {
  open: boolean
  mode: 'create' | 'edit'
  strategy?: Strategy
}

const emptyStrategy = (): Partial<Strategy> => ({
  name: '',
  description: '',
  conditions: [],
})

export default function StrategiesPage() {
  const { mutate } = useSWRConfig()
  const { data: strategiesRes, isLoading } = useSWR<SavedStrategiesResponse>(SWR_KEY, fetchAPI)
  const strategies = strategiesRes?.strategies
  const [dialog, setDialog] = useState<DialogState>({ open: false, mode: 'create' })
  const [form, setForm] = useState<Partial<Strategy>>(emptyStrategy())
  const [deleteId, setDeleteId] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const openCreate = () => {
    setForm(emptyStrategy())
    setDialog({ open: true, mode: 'create' })
  }

  const openEdit = (s: Strategy) => {
    setForm({ ...s, conditions: [...s.conditions] })
    setDialog({ open: true, mode: 'edit', strategy: s })
  }

  const closeDialog = () => setDialog({ open: false, mode: 'create' })

  const addCondition = () => {
    setForm(prev => ({
      ...prev,
      conditions: [...(prev.conditions ?? []), { field: 'pe', operator: 'lt', value: 20 }],
    }))
  }

  const updateCondition = (i: number, patch: Partial<StrategyCondition>) => {
    setForm(prev => {
      const conds = [...(prev.conditions ?? [])]
      conds[i] = { ...conds[i], ...patch }
      return { ...prev, conditions: conds }
    })
  }

  const removeCondition = (i: number) => {
    setForm(prev => {
      const conds = [...(prev.conditions ?? [])]
      conds.splice(i, 1)
      return { ...prev, conditions: conds }
    })
  }

  const handleSave = async () => {
    if (!form.name?.trim()) return
    setSaving(true)
    try {
      if (dialog.mode === 'create') {
        await fetchAPI(SWR_KEY, { method: 'POST', body: JSON.stringify(form) })
      } else if (dialog.strategy) {
        await fetchAPI(`${SWR_KEY}/${dialog.strategy.id}`, { method: 'PUT', body: JSON.stringify(form) })
      }
      await mutate(SWR_KEY)
      closeDialog()
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id: string) => {
    await fetchAPI(`${SWR_KEY}/${id}`, { method: 'DELETE' })
    await mutate(SWR_KEY)
    setDeleteId(null)
  }

  return (
    <div>
      <div className="mb-6 flex justify-between items-start">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: 'var(--foreground)' }}>策略管理</h1>
          <p className="text-sm mt-1" style={{ color: 'var(--muted-foreground)' }}>自訂選股策略 CRUD 管理</p>
        </div>
        <button
          onClick={openCreate}
          className="h-9 px-4 rounded-md text-sm font-medium"
          style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}
        >
          新增策略
        </button>
      </div>

      {isLoading ? (
        <div className="space-y-2">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-24 rounded-lg animate-pulse" style={{ background: 'var(--card)' }} />
          ))}
        </div>
      ) : strategies && strategies.length > 0 ? (
        <div className="space-y-3">
          {strategies.map((s) => (
            <div
              key={s.id}
              className="rounded-lg p-4"
              style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
            >
              <div className="flex justify-between items-start mb-2">
                <div>
                  <h3 className="font-semibold" style={{ color: 'var(--foreground)' }}>{s.name}</h3>
                  {s.description && (
                    <p className="text-sm mt-0.5" style={{ color: 'var(--muted-foreground)' }}>{s.description}</p>
                  )}
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => openEdit(s)}
                    className="h-8 px-3 rounded-md text-xs font-medium"
                    style={{ background: 'var(--secondary)', color: 'var(--foreground)' }}
                  >
                    編輯
                  </button>
                  <button
                    onClick={() => setDeleteId(s.id)}
                    className="h-8 px-3 rounded-md text-xs font-medium"
                    style={{ background: 'var(--destructive)', color: 'var(--destructive-foreground)' }}
                  >
                    刪除
                  </button>
                </div>
              </div>
              <div className="flex flex-wrap gap-2 mt-2">
                {s.conditions.map((c, i) => {
                  const fieldLabel = FIELDS.find(f => f.key === c.field)?.label ?? c.field
                  const opLabel = OPERATORS.find(o => o.key === c.operator)?.label ?? c.operator
                  return (
                    <span
                      key={i}
                      className="text-xs px-2 py-1 rounded-full"
                      style={{ background: 'var(--secondary)', color: 'var(--foreground)' }}
                    >
                      {fieldLabel} {opLabel} {c.value}
                    </span>
                  )
                })}
              </div>
              <p className="text-xs mt-2" style={{ color: 'var(--muted-foreground)' }}>
                建立：{s.createdAt.slice(0, 10)}
              </p>
            </div>
          ))}
        </div>
      ) : (
        <div
          className="rounded-lg p-12 text-center"
          style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
        >
          <p className="text-lg" style={{ color: 'var(--muted-foreground)' }}>尚無策略，點擊新增策略開始建立</p>
        </div>
      )}

      {/* 新增/編輯 Dialog */}
      {dialog.open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: 'rgba(0,0,0,0.7)' }}>
          <div
            className="w-full max-w-lg rounded-lg p-6"
            style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
          >
            <h2 className="text-lg font-semibold mb-4" style={{ color: 'var(--foreground)' }}>
              {dialog.mode === 'create' ? '新增策略' : '編輯策略'}
            </h2>

            <div className="space-y-3 mb-4">
              <div>
                <label className="block text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>策略名稱</label>
                <input
                  type="text"
                  value={form.name ?? ''}
                  onChange={(e) => setForm(prev => ({ ...prev, name: e.target.value }))}
                  className="h-9 w-full rounded-md border px-3 text-sm"
                  style={{ background: 'var(--background)', border: '1px solid var(--border)', color: 'var(--foreground)' }}
                />
              </div>
              <div>
                <label className="block text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>描述（選填）</label>
                <input
                  type="text"
                  value={form.description ?? ''}
                  onChange={(e) => setForm(prev => ({ ...prev, description: e.target.value }))}
                  className="h-9 w-full rounded-md border px-3 text-sm"
                  style={{ background: 'var(--background)', border: '1px solid var(--border)', color: 'var(--foreground)' }}
                />
              </div>

              {/* 條件列表 */}
              <div>
                <div className="flex justify-between items-center mb-2">
                  <label className="text-xs" style={{ color: 'var(--muted-foreground)' }}>篩選條件</label>
                  <button
                    onClick={addCondition}
                    className="text-xs px-2 py-1 rounded"
                    style={{ background: 'var(--secondary)', color: 'var(--foreground)' }}
                  >
                    + 新增條件
                  </button>
                </div>
                <div className="space-y-2">
                  {(form.conditions ?? []).map((c, i) => (
                    <div key={i} className="flex gap-2 items-center">
                      <select
                        value={c.field}
                        onChange={(e) => updateCondition(i, { field: e.target.value })}
                        className="flex-1 h-8 rounded border px-2 text-xs"
                        style={{ background: 'var(--background)', border: '1px solid var(--border)', color: 'var(--foreground)' }}
                      >
                        {FIELDS.map(f => <option key={f.key} value={f.key}>{f.label}</option>)}
                      </select>
                      <select
                        value={c.operator}
                        onChange={(e) => updateCondition(i, { operator: e.target.value as StrategyCondition['operator'] })}
                        className="w-14 h-8 rounded border px-1 text-xs"
                        style={{ background: 'var(--background)', border: '1px solid var(--border)', color: 'var(--foreground)' }}
                      >
                        {OPERATORS.map(o => <option key={o.key} value={o.key}>{o.label}</option>)}
                      </select>
                      <input
                        type="number"
                        value={c.value}
                        onChange={(e) => updateCondition(i, { value: Number(e.target.value) })}
                        className="w-20 h-8 rounded border px-2 text-xs"
                        style={{ background: 'var(--background)', border: '1px solid var(--border)', color: 'var(--foreground)' }}
                      />
                      <button
                        onClick={() => removeCondition(i)}
                        className="text-xs px-2 py-1 rounded"
                        style={{ color: 'var(--destructive)' }}
                      >
                        x
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="flex justify-end gap-2">
              <button
                onClick={closeDialog}
                className="h-9 px-4 rounded-md text-sm font-medium"
                style={{ background: 'var(--secondary)', color: 'var(--foreground)' }}
              >
                取消
              </button>
              <button
                onClick={handleSave}
                disabled={saving}
                className="h-9 px-4 rounded-md text-sm font-medium disabled:opacity-60"
                style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}
              >
                {saving ? '儲存中...' : '儲存'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 刪除確認 Dialog */}
      {deleteId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: 'rgba(0,0,0,0.7)' }}>
          <div
            className="w-full max-w-sm rounded-lg p-6"
            style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
          >
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--foreground)' }}>確認刪除</h2>
            <p className="text-sm mb-4" style={{ color: 'var(--muted-foreground)' }}>
              確定要刪除此策略嗎？此操作無法復原。
            </p>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setDeleteId(null)}
                className="h-9 px-4 rounded-md text-sm font-medium"
                style={{ background: 'var(--secondary)', color: 'var(--foreground)' }}
              >
                取消
              </button>
              <button
                onClick={() => handleDelete(deleteId)}
                className="h-9 px-4 rounded-md text-sm font-medium"
                style={{ background: 'var(--destructive)', color: 'var(--destructive-foreground)' }}
              >
                確認刪除
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
