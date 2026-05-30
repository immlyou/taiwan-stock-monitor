'use client'

import { useState } from 'react'
import useSWR, { mutate } from 'swr'
import { fetchAPI } from '@/lib/api/client'
import { KpiCard } from '@/components/shared/KpiCard'
import { getChangeColorVar } from '@/lib/utils/format'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog'

interface Holding {
  stock_id: string
  shares: number
  cost_price: number
  buy_date?: string
  name?: string
  current_price?: number
  current_value?: number
  cost_value?: number
  pnl?: number
  pnl_pct?: number
}

interface PortfolioSummary {
  total_cost: number
  total_value: number
  total_pnl: number
  total_pnl_pct: number
}

interface PortfolioDetail {
  id: string
  name: string
  description: string
  holdings: Holding[]
  summary: PortfolioSummary
}

interface PortfolioDiagnostics {
  concentration: {
    top_holding_weight: number
    top_industry_weight: number
  }
  risk: {
    annualized_volatility_pct: number
    max_drawdown_pct: number
  }
  allocation: Array<{ industry: string; weight: number; market_value: number }>
  suggestions: string[]
}

const PORTFOLIO_ID = 'default'
const SWR_KEY = `/portfolios/${PORTFOLIO_ID}`

export default function PortfolioPage() {
  const { data, isLoading, error } = useSWR<PortfolioDetail>(SWR_KEY, fetchAPI)
  const { data: diagnostics } = useSWR<PortfolioDiagnostics>(`${SWR_KEY}/diagnostics`, fetchAPI)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editHolding, setEditHolding] = useState<Holding | null>(null)
  const [deleteStockId, setDeleteStockId] = useState<string | null>(null)
  const [form, setForm] = useState({
    stock_id: '',
    shares: '',
    cost_price: '',
  })
  const [saving, setSaving] = useState(false)

  const openAdd = () => {
    setEditHolding(null)
    setForm({ stock_id: '', shares: '', cost_price: '' })
    setDialogOpen(true)
  }

  const openEdit = (h: Holding) => {
    setEditHolding(h)
    setForm({ stock_id: h.stock_id, shares: String(h.shares), cost_price: String(h.cost_price) })
    setDialogOpen(true)
  }

  const buildUpdatedHoldings = (
    current: Holding[],
    action: 'add' | 'edit' | 'delete',
    payload?: { stock_id: string; shares: number; cost_price: number } | string
  ): Array<{ stock_id: string; shares: number; cost_price: number }> => {
    const clean = current.map(h => ({
      stock_id: h.stock_id,
      shares: h.shares,
      cost_price: h.cost_price,
    }))
    if (action === 'delete' && typeof payload === 'string') {
      return clean.filter(h => h.stock_id !== payload)
    }
    if (action === 'add' && typeof payload === 'object') {
      return [...clean, payload]
    }
    if (action === 'edit' && typeof payload === 'object') {
      return clean.map(h => (h.stock_id === payload.stock_id ? { ...h, ...payload } : h))
    }
    return clean
  }

  const ensurePortfolioExists = async () => {
    try {
      await fetchAPI(SWR_KEY)
    } catch {
      await fetchAPI('/portfolios', {
        method: 'POST',
        body: JSON.stringify({ name: PORTFOLIO_ID, description: '預設組合' }),
      })
    }
  }

  const handleSave = async () => {
    if (!form.stock_id.trim() || !form.shares || !form.cost_price) return
    setSaving(true)
    try {
      await ensurePortfolioExists()
      const current = data?.holdings ?? []
      const payload = {
        stock_id: form.stock_id.toUpperCase(),
        shares: Number(form.shares),
        cost_price: Number(form.cost_price),
      }
      const updated = buildUpdatedHoldings(current, editHolding ? 'edit' : 'add', payload)
      await fetchAPI(SWR_KEY, {
        method: 'PUT',
        body: JSON.stringify({ holdings: updated }),
      })
      await mutate(SWR_KEY)
      setDialogOpen(false)
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (stock_id: string) => {
    const current = data?.holdings ?? []
    const updated = buildUpdatedHoldings(current, 'delete', stock_id)
    await fetchAPI(SWR_KEY, {
      method: 'PUT',
      body: JSON.stringify({ holdings: updated }),
    })
    await mutate(SWR_KEY)
    setDeleteStockId(null)
  }

  const summary = data?.summary
  const holdings = data?.holdings ?? []

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

      {error && !data ? (
        <div
          className="rounded-lg p-8 text-center"
          style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
        >
          <p style={{ color: 'var(--muted-foreground)' }}>尚無投資組合，點擊新增持股建立預設組合</p>
        </div>
      ) : isLoading ? (
        <div className="space-y-3">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {[...Array(4)].map((_, i) => <KpiCard key={i} title="" value="" isLoading />)}
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          {/* 總覽 KPI */}
          {summary && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <KpiCard
                title="總市值"
                value={`${(summary.total_value / 1e4).toFixed(1)} 萬`}
                accentColor="var(--primary)"
              />
              <KpiCard
                title="未實現損益"
                value={`${summary.total_pnl > 0 ? '+' : ''}${(summary.total_pnl / 1e4).toFixed(1)} 萬`}
                subValue={`${summary.total_pnl_pct > 0 ? '+' : ''}${summary.total_pnl_pct.toFixed(2)}%`}
                accentColor={summary.total_pnl >= 0 ? 'var(--stock-up)' : 'var(--stock-down)'}
              />
              <KpiCard
                title="持股成本"
                value={`${(summary.total_cost / 1e4).toFixed(1)} 萬`}
                accentColor="var(--muted-foreground)"
              />
              <KpiCard
                title="持股數"
                value={`${holdings.length} 支`}
                accentColor="#f59e0b"
              />
            </div>
          )}

          {diagnostics && holdings.length > 0 && (
            <div
              className="rounded-lg p-4"
              style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
            >
              <div className="flex items-center justify-between mb-3">
                <div>
                  <h3 className="text-sm font-medium" style={{ color: 'var(--foreground)' }}>投資組合診斷</h3>
                  <p className="text-xs mt-0.5" style={{ color: 'var(--muted-foreground)' }}>集中度、風險與產業配置</p>
                </div>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
                <KpiCard title="最大持股權重" value={`${diagnostics.concentration.top_holding_weight.toFixed(1)}%`} accentColor="#f59e0b" />
                <KpiCard title="最大產業權重" value={`${diagnostics.concentration.top_industry_weight.toFixed(1)}%`} accentColor="#8b5cf6" />
                <KpiCard title="年化波動率" value={`${diagnostics.risk.annualized_volatility_pct.toFixed(1)}%`} accentColor="var(--primary)" />
                <KpiCard title="最大回撤" value={`${diagnostics.risk.max_drawdown_pct.toFixed(1)}%`} accentColor="var(--destructive)" />
              </div>
              <div className="grid md:grid-cols-2 gap-3">
                <div className="rounded-md p-3" style={{ background: 'var(--secondary)' }}>
                  <p className="text-xs mb-2" style={{ color: 'var(--muted-foreground)' }}>產業配置</p>
                  <div className="space-y-2">
                    {diagnostics.allocation.slice(0, 5).map((item) => (
                      <div key={item.industry}>
                        <div className="flex justify-between text-xs mb-1">
                          <span style={{ color: 'var(--foreground)' }}>{item.industry}</span>
                          <span style={{ color: 'var(--muted-foreground)' }}>{item.weight.toFixed(1)}%</span>
                        </div>
                        <div className="h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--border)' }}>
                          <div className="h-full rounded-full" style={{ width: `${Math.min(100, item.weight)}%`, background: 'var(--primary)' }} />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
                <div className="rounded-md p-3" style={{ background: 'var(--secondary)' }}>
                  <p className="text-xs mb-2" style={{ color: 'var(--muted-foreground)' }}>調整建議</p>
                  <div className="space-y-2">
                    {diagnostics.suggestions.map((suggestion) => (
                      <p key={suggestion} className="text-sm" style={{ color: 'var(--foreground)' }}>{suggestion}</p>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* 持股表格 */}
          <div
            className="rounded-lg overflow-hidden"
            style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
          >
            <div className="px-4 py-3 border-b" style={{ borderColor: 'var(--border)' }}>
              <h3 className="text-sm font-medium" style={{ color: 'var(--foreground)' }}>
                持股明細（{holdings.length} 支）
              </h3>
            </div>
            {holdings.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr style={{ background: 'var(--secondary)' }}>
                      {['代號', '名稱', '持股（張）', '成本價', '現價', '市值', '未實現損益', '報酬率', '操作'].map(h => (
                        <th key={h} className="text-left py-2 px-4" style={{ color: 'var(--muted-foreground)' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {holdings.map((h) => {
                      const pnl = h.pnl ?? 0
                      const pnlPct = h.pnl_pct ?? 0
                      const currentPrice = h.current_price ?? h.cost_price
                      const marketValue = h.current_value ?? h.shares * h.cost_price
                      return (
                        <tr key={h.stock_id} style={{ borderBottom: '1px solid var(--border)' }}>
                          <td className="py-2 px-4 font-medium" style={{ color: 'var(--primary)' }}>{h.stock_id}</td>
                          <td className="py-2 px-4" style={{ color: 'var(--foreground)' }}>{h.name ?? '—'}</td>
                          <td className="py-2 px-4 tabular-nums" style={{ color: 'var(--foreground)' }}>{h.shares}</td>
                          <td className="py-2 px-4 tabular-nums" style={{ color: 'var(--foreground)' }}>{h.cost_price.toFixed(2)}</td>
                          <td className="py-2 px-4 tabular-nums" style={{ color: 'var(--foreground)' }}>{currentPrice.toFixed(2)}</td>
                          <td className="py-2 px-4 tabular-nums" style={{ color: 'var(--foreground)' }}>
                            {(marketValue / 1e4).toFixed(1)} 萬
                          </td>
                          <td
                            className="py-2 px-4 tabular-nums font-medium"
                            style={{ color: getChangeColorVar(pnl) }}
                          >
                            {pnl > 0 ? '+' : ''}{(pnl / 1e4).toFixed(1)} 萬
                          </td>
                          <td
                            className="py-2 px-4 tabular-nums font-semibold"
                            style={{ color: getChangeColorVar(pnlPct) }}
                          >
                            {pnlPct > 0 ? '+' : ''}{pnlPct.toFixed(2)}%
                          </td>
                          <td className="py-2 px-4">
                            <div className="flex gap-1">
                              <button
                                onClick={() => openEdit(h)}
                                className="text-xs px-2 py-1 rounded"
                                style={{ background: 'var(--secondary)', color: 'var(--foreground)' }}
                              >
                                編輯
                              </button>
                              <button
                                onClick={() => setDeleteStockId(h.stock_id)}
                                className="text-xs px-2 py-1 rounded"
                                style={{ color: 'var(--destructive)' }}
                              >
                                刪除
                              </button>
                            </div>
                          </td>
                        </tr>
                      )
                    })}
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
      )}

      {/* 新增/編輯 Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent
          className="max-w-sm"
          style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
        >
          <DialogHeader>
            <DialogTitle style={{ color: 'var(--foreground)' }}>
              {editHolding ? '編輯持股' : '新增持股'}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <label className="block text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>股票代號</label>
              <input
                type="text"
                value={form.stock_id}
                onChange={(e) => setForm(p => ({ ...p, stock_id: e.target.value.toUpperCase() }))}
                disabled={!!editHolding}
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
              <label className="block text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>成本價（元/股）</label>
              <input
                type="number"
                value={form.cost_price}
                onChange={(e) => setForm(p => ({ ...p, cost_price: e.target.value }))}
                placeholder="例：580"
                className="h-9 w-full rounded-md border px-3 text-sm"
                style={{ background: 'var(--background)', border: '1px solid var(--border)', color: 'var(--foreground)' }}
              />
            </div>
          </div>
          <DialogFooter className="mt-4 flex justify-end gap-2">
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
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 刪除確認 */}
      <Dialog open={!!deleteStockId} onOpenChange={(open) => { if (!open) setDeleteStockId(null) }}>
        <DialogContent
          className="max-w-sm"
          style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
        >
          <DialogHeader>
            <DialogTitle style={{ color: 'var(--foreground)' }}>確認刪除</DialogTitle>
            <DialogDescription style={{ color: 'var(--muted-foreground)' }}>
              確定要移除 {deleteStockId} 的持股紀錄嗎？
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="flex justify-end gap-2">
            <button onClick={() => setDeleteStockId(null)} className="h-9 px-4 rounded-md text-sm" style={{ background: 'var(--secondary)', color: 'var(--foreground)' }}>
              取消
            </button>
            <button onClick={() => deleteStockId && handleDelete(deleteStockId)} className="h-9 px-4 rounded-md text-sm" style={{ background: 'var(--destructive)', color: 'var(--destructive-foreground)' }}>
              刪除
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
