'use client'

import { useState } from 'react'
import useSWR, { mutate } from 'swr'
import { fetchAPI } from '@/lib/api/client'
import { KpiCard } from '@/components/shared/KpiCard'
import { getChangeColorVar } from '@/lib/utils/format'

interface Position {
  id: string
  code: string
  name: string
  shares: number
  avgCost: number
  currentPrice: number
  marketValue: number
  unrealizedPnl: number
  unrealizedPnlPercent: number
  costBasis: number
}

interface PortfolioSummary {
  totalMarketValue: number
  totalCostBasis: number
  totalUnrealizedPnl: number
  totalUnrealizedPnlPercent: number
  cashBalance: number
  positions: Position[]
}

const SWR_KEY = '/portfolios/default'

export default function PortfolioPage() {
  const { data, isLoading, error } = useSWR<PortfolioSummary>(SWR_KEY, fetchAPI)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editPosition, setEditPosition] = useState<Position | null>(null)
  const [deleteId, setDeleteId] = useState<string | null>(null)
  const [form, setForm] = useState({
    code: '',
    shares: '',
    avgCost: '',
  })
  const [saving, setSaving] = useState(false)

  const openAdd = () => {
    setEditPosition(null)
    setForm({ code: '', shares: '', avgCost: '' })
    setDialogOpen(true)
  }

  const openEdit = (pos: Position) => {
    setEditPosition(pos)
    setForm({ code: pos.code, shares: String(pos.shares), avgCost: String(pos.avgCost) })
    setDialogOpen(true)
  }

  const handleSave = async () => {
    if (!form.code.trim() || !form.shares || !form.avgCost) return
    setSaving(true)
    try {
      if (editPosition) {
        await fetchAPI(`${SWR_KEY}/positions/${editPosition.id}`, {
          method: 'PUT',
          body: JSON.stringify({ shares: Number(form.shares), avgCost: Number(form.avgCost) }),
        })
      } else {
        await fetchAPI(`${SWR_KEY}/positions`, {
          method: 'POST',
          body: JSON.stringify({ code: form.code.toUpperCase(), shares: Number(form.shares), avgCost: Number(form.avgCost) }),
        })
      }
      await mutate(SWR_KEY)
      setDialogOpen(false)
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id: string) => {
    await fetchAPI(`${SWR_KEY}/positions/${id}`, { method: 'DELETE' })
    await mutate(SWR_KEY)
    setDeleteId(null)
  }

  return (
    <div>
      <div className="mb-6 flex justify-between items-start">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: 'var(--foreground)' }}>投資組合</h1>
          <p className="text-sm mt-1" style={{ color: 'var(--muted-foreground)' }}>持股明細與損益追蹤</p>
        </div>
        <button
          onClick={openAdd}
          className="h-9 px-4 rounded-md text-sm font-medium"
          style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}
        >
          新增持股
        </button>
      </div>

      {error ? (
        <div className="rounded-lg p-6 text-center" style={{ background: 'var(--card)', border: '1px solid var(--border)' }}>
          <p style={{ color: 'var(--destructive)' }}>資料載入失敗</p>
        </div>
      ) : isLoading ? (
        <div className="space-y-3">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {[...Array(4)].map((_, i) => <KpiCard key={i} title="" value="" isLoading />)}
          </div>
        </div>
      ) : data ? (
        <div className="space-y-4">
          {/* 總覽 KPI */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <KpiCard
              title="總市值"
              value={`${(data.totalMarketValue / 1e4).toFixed(1)} 萬`}
              accentColor="var(--primary)"
            />
            <KpiCard
              title="未實現損益"
              value={`${data.totalUnrealizedPnl > 0 ? '+' : ''}${(data.totalUnrealizedPnl / 1e4).toFixed(1)} 萬`}
              subValue={`${data.totalUnrealizedPnlPercent > 0 ? '+' : ''}${data.totalUnrealizedPnlPercent.toFixed(2)}%`}
              accentColor={data.totalUnrealizedPnl >= 0 ? 'var(--stock-up)' : 'var(--stock-down)'}
            />
            <KpiCard
              title="持股成本"
              value={`${(data.totalCostBasis / 1e4).toFixed(1)} 萬`}
              accentColor="var(--muted-foreground)"
            />
            <KpiCard
              title="現金餘額"
              value={`${(data.cashBalance / 1e4).toFixed(1)} 萬`}
              accentColor="#f59e0b"
            />
          </div>

          {/* 持股表格 */}
          <div
            className="rounded-lg overflow-hidden"
            style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
          >
            <div className="px-4 py-3 border-b" style={{ borderColor: 'var(--border)' }}>
              <h3 className="text-sm font-medium" style={{ color: 'var(--foreground)' }}>
                持股明細（{data.positions.length} 支）
              </h3>
            </div>
            {data.positions.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr style={{ background: 'var(--secondary)' }}>
                      {['代號', '名稱', '持股（張）', '均成本', '現價', '市值', '未實現損益', '報酬率', '操作'].map(h => (
                        <th key={h} className="text-left py-2 px-4" style={{ color: 'var(--muted-foreground)' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {data.positions.map((pos) => (
                      <tr key={pos.id} style={{ borderBottom: '1px solid var(--border)' }}>
                        <td className="py-2 px-4 font-medium" style={{ color: 'var(--primary)' }}>{pos.code}</td>
                        <td className="py-2 px-4" style={{ color: 'var(--foreground)' }}>{pos.name}</td>
                        <td className="py-2 px-4 tabular-nums" style={{ color: 'var(--foreground)' }}>{pos.shares}</td>
                        <td className="py-2 px-4 tabular-nums" style={{ color: 'var(--foreground)' }}>{pos.avgCost.toFixed(2)}</td>
                        <td className="py-2 px-4 tabular-nums" style={{ color: 'var(--foreground)' }}>{pos.currentPrice.toFixed(2)}</td>
                        <td className="py-2 px-4 tabular-nums" style={{ color: 'var(--foreground)' }}>
                          {(pos.marketValue / 1e4).toFixed(1)} 萬
                        </td>
                        <td
                          className="py-2 px-4 tabular-nums font-medium"
                          style={{ color: getChangeColorVar(pos.unrealizedPnl) }}
                        >
                          {pos.unrealizedPnl > 0 ? '+' : ''}{(pos.unrealizedPnl / 1e4).toFixed(1)} 萬
                        </td>
                        <td
                          className="py-2 px-4 tabular-nums font-semibold"
                          style={{ color: getChangeColorVar(pos.unrealizedPnlPercent) }}
                        >
                          {pos.unrealizedPnlPercent > 0 ? '+' : ''}{pos.unrealizedPnlPercent.toFixed(2)}%
                        </td>
                        <td className="py-2 px-4">
                          <div className="flex gap-1">
                            <button
                              onClick={() => openEdit(pos)}
                              className="text-xs px-2 py-1 rounded"
                              style={{ background: 'var(--secondary)', color: 'var(--foreground)' }}
                            >
                              編輯
                            </button>
                            <button
                              onClick={() => setDeleteId(pos.id)}
                              className="text-xs px-2 py-1 rounded"
                              style={{ color: 'var(--destructive)' }}
                            >
                              刪除
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="p-8 text-center">
                <p style={{ color: 'var(--muted-foreground)' }}>尚無持股，點擊新增持股開始建立</p>
              </div>
            )}
          </div>
        </div>
      ) : null}

      {/* 新增/編輯 Dialog */}
      {dialogOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: 'rgba(0,0,0,0.7)' }}>
          <div
            className="w-full max-w-sm rounded-lg p-6"
            style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
          >
            <h2 className="text-lg font-semibold mb-4" style={{ color: 'var(--foreground)' }}>
              {editPosition ? '編輯持股' : '新增持股'}
            </h2>
            <div className="space-y-3">
              <div>
                <label className="block text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>股票代號</label>
                <input
                  type="text"
                  value={form.code}
                  onChange={(e) => setForm(p => ({ ...p, code: e.target.value.toUpperCase() }))}
                  disabled={!!editPosition}
                  placeholder="例：2330"
                  className="h-9 w-full rounded-md border px-3 text-sm disabled:opacity-60"
                  style={{ background: 'var(--background)', border: '1px solid var(--border)', color: 'var(--foreground)' }}
                />
              </div>
              <div>
                <label className="block text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>持股張數</label>
                <input
                  type="number"
                  value={form.shares}
                  onChange={(e) => setForm(p => ({ ...p, shares: e.target.value }))}
                  placeholder="例：10"
                  className="h-9 w-full rounded-md border px-3 text-sm"
                  style={{ background: 'var(--background)', border: '1px solid var(--border)', color: 'var(--foreground)' }}
                />
              </div>
              <div>
                <label className="block text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>平均成本（元/股）</label>
                <input
                  type="number"
                  value={form.avgCost}
                  onChange={(e) => setForm(p => ({ ...p, avgCost: e.target.value }))}
                  placeholder="例：580"
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
                onClick={handleSave}
                disabled={saving}
                className="h-9 px-4 rounded-md text-sm disabled:opacity-60"
                style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}
              >
                {saving ? '儲存中...' : '儲存'}
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
            <p className="text-sm mb-4" style={{ color: 'var(--muted-foreground)' }}>確定要移除此持股紀錄嗎？</p>
            <div className="flex justify-end gap-2">
              <button onClick={() => setDeleteId(null)} className="h-9 px-4 rounded-md text-sm" style={{ background: 'var(--secondary)', color: 'var(--foreground)' }}>
                取消
              </button>
              <button onClick={() => handleDelete(deleteId)} className="h-9 px-4 rounded-md text-sm" style={{ background: 'var(--destructive)', color: 'var(--destructive-foreground)' }}>
                刪除
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
