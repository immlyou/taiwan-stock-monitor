'use client'

import React, { useState } from 'react'
import useSWR, { mutate } from 'swr'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { fetchAPI } from '@/lib/api/client'
import { formatPrice, formatCurrency } from '@/lib/utils/format'

interface JournalEntry {
  id: string
  date: string
  stock_id: string
  action: string
  shares: number | null
  price: number | null
  note: string
  created_at: string
}

interface JournalResponse {
  entries: JournalEntry[]
  total: number
}

const SWR_KEY_BASE = '/journal'

const ACTION_LABELS: Record<string, { label: string; color: string }> = {
  buy: { label: '買入', color: 'var(--stock-up)' },
  sell: { label: '賣出', color: 'var(--stock-down)' },
  add: { label: '加碼', color: 'var(--stock-up)' },
  reduce: { label: '減碼', color: 'var(--stock-down)' },
  note: { label: '備注', color: 'var(--muted-foreground)' },
}

// 深色主題 Markdown 元件對應（取代脆弱的逐行手刻 renderMarkdown）
const fg = { color: 'var(--foreground)' }
const muted = { color: 'var(--muted-foreground)' }
const MD_COMPONENTS = {
  h1: (p: React.ComponentProps<'h1'>) => <h1 className="text-xl font-bold mt-5 mb-2" style={fg} {...p} />,
  h2: (p: React.ComponentProps<'h2'>) => <h2 className="text-lg font-bold mt-4 mb-2" style={fg} {...p} />,
  h3: (p: React.ComponentProps<'h3'>) => <h3 className="text-base font-semibold mt-3 mb-1" style={fg} {...p} />,
  p: (p: React.ComponentProps<'p'>) => <p className="text-sm leading-relaxed my-2" style={fg} {...p} />,
  ul: (p: React.ComponentProps<'ul'>) => <ul className="list-disc ml-5 my-2 space-y-1 text-sm" style={fg} {...p} />,
  ol: (p: React.ComponentProps<'ol'>) => <ol className="list-decimal ml-5 my-2 space-y-1 text-sm" style={fg} {...p} />,
  li: (p: React.ComponentProps<'li'>) => <li className="text-sm leading-relaxed" style={fg} {...p} />,
  strong: (p: React.ComponentProps<'strong'>) => <strong className="font-semibold" style={fg} {...p} />,
  em: (p: React.ComponentProps<'em'>) => <em style={fg} {...p} />,
  a: (p: React.ComponentProps<'a'>) => <a className="underline" style={{ color: 'var(--primary)' }} target="_blank" rel="noopener noreferrer" {...p} />,
  blockquote: (p: React.ComponentProps<'blockquote'>) => <blockquote className="border-l-2 pl-3 my-2 text-sm" style={{ ...muted, borderColor: 'var(--border)' }} {...p} />,
  hr: () => <hr className="my-3" style={{ borderColor: 'var(--border)' }} />,
  code: (p: React.ComponentProps<'code'>) => <code className="px-1 py-0.5 rounded text-xs font-mono" style={{ background: 'var(--secondary)', color: 'var(--foreground)' }} {...p} />,
  table: (p: React.ComponentProps<'table'>) => <div className="overflow-x-auto my-2"><table className="w-full text-sm border-collapse" {...p} /></div>,
  th: (p: React.ComponentProps<'th'>) => <th className="text-left px-2 py-1 font-medium border-b" style={{ ...muted, borderColor: 'var(--border)' }} {...p} />,
  td: (p: React.ComponentProps<'td'>) => <td className="px-2 py-1 border-b tabular-nums" style={{ ...fg, borderColor: 'var(--border)' }} {...p} />,
}

function MarkdownReport({ children }: { children: string }) {
  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={MD_COMPONENTS}>
      {children}
    </ReactMarkdown>
  )
}

const FILTER_CHIPS: { key: string; label: string }[] = [
  { key: 'all', label: '全部' },
  { key: 'buy', label: ACTION_LABELS.buy.label },
  { key: 'sell', label: ACTION_LABELS.sell.label },
  { key: 'add', label: ACTION_LABELS.add.label },
  { key: 'reduce', label: ACTION_LABELS.reduce.label },
]

export default function JournalPage() {
  const [limit] = useState(50)
  const [actionFilter, setActionFilter] = useState<string>('all')
  const [dialogOpen, setDialogOpen] = useState(false)
  const [deleteId, setDeleteId] = useState<string | null>(null)
  const [form, setForm] = useState({
    date: new Date().toISOString().slice(0, 10),
    stock_id: '',
    action: 'buy' as string,
    shares: '',
    price: '',
    note: '',
  })
  const [saving, setSaving] = useState(false)
  const [aiReport, setAiReport] = useState<string | null>(null)
  const [aiLoading, setAiLoading] = useState(false)

  const swrKey = `${SWR_KEY_BASE}?limit=${limit}`
  const { data, isLoading, error } = useSWR<JournalResponse>(swrKey, fetchAPI)

  const filteredEntries = (data?.entries ?? []).filter(
    (e) => actionFilter === 'all' || e.action === actionFilter
  )

  const handleCreate = async () => {
    if (!form.stock_id.trim()) return
    setSaving(true)
    try {
      await fetchAPI(SWR_KEY_BASE, {
        method: 'POST',
        body: JSON.stringify({
          date: form.date,
          stock_id: form.stock_id.toUpperCase(),
          action: form.action,
          shares: form.shares ? Number(form.shares) : null,
          price: form.price ? Number(form.price) : null,
          note: form.note || '',
        }),
      })
      await mutate(swrKey)
      setDialogOpen(false)
      setForm({ date: new Date().toISOString().slice(0, 10), stock_id: '', action: 'buy', shares: '', price: '', note: '' })
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id: string) => {
    await fetchAPI(`${SWR_KEY_BASE}/${id}`, { method: 'DELETE' })
    await mutate(swrKey)
    setDeleteId(null)
  }

  const handleAiReview = async () => {
    if (!data || data.entries.length === 0) return
    setAiLoading(true)
    setAiReport(null)
    try {
      const result = await fetchAPI<{ report?: string; error?: string }>('/ai/journal-review', {
        method: 'POST',
        body: JSON.stringify({ entries: data.entries }),
      }, 60000)
      setAiReport(result.report ?? '無法取得報告內容')
    } catch {
      setAiReport('AI 回顧報告產生失敗，請稍後再試。')
    } finally {
      setAiLoading(false)
    }
  }

  const estimatedAmount = form.shares && form.price
    ? formatCurrency(Number(form.shares) * 1000 * Number(form.price), { compact: true })
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
          {data && data.entries.length > 0 && (
            <div className="mb-3 flex flex-wrap gap-2">
              {FILTER_CHIPS.map((chip) => {
                const active = actionFilter === chip.key
                const chipColor = ACTION_LABELS[chip.key]?.color ?? 'var(--foreground)'
                return (
                  <button
                    key={chip.key}
                    onClick={() => setActionFilter(chip.key)}
                    className="h-8 px-3 rounded-full text-xs font-medium border"
                    style={{
                      background: active ? chipColor : 'var(--secondary)',
                      color: active ? '#fff' : 'var(--foreground)',
                      borderColor: active ? chipColor : 'var(--border)',
                    }}
                  >
                    {chip.label}
                  </button>
                )
              })}
            </div>
          )}
          <div
            className="rounded-lg overflow-hidden mb-4"
            style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
          >
          {data && data.entries.length > 0 ? (
            filteredEntries.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr style={{ background: 'var(--secondary)' }}>
                    {['日期', '代號', '操作', '張數', '成交價', '預估金額', '備注', '操作'].map(h => (
                      <th key={h} className="text-left py-2 px-4" style={{ color: 'var(--muted-foreground)', whiteSpace: 'nowrap' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filteredEntries.map((e) => {
                    const actionInfo = ACTION_LABELS[e.action] ?? { label: e.action, color: 'var(--foreground)' }
                    const amount = e.shares && e.price ? e.shares * 1000 * e.price : null
                    return (
                      <tr key={e.id} style={{ borderBottom: '1px solid var(--border)' }}>
                        <td className="py-2 px-4 tabular-nums" style={{ color: 'var(--muted-foreground)', whiteSpace: 'nowrap' }}>{e.date}</td>
                        <td className="py-2 px-4 font-medium" style={{ color: 'var(--primary)' }}>{e.stock_id}</td>
                        <td className="py-2 px-4 font-semibold" style={{ color: actionInfo.color }}>{actionInfo.label}</td>
                        <td className="py-2 px-4 tabular-nums" style={{ color: 'var(--foreground)' }}>{e.shares ?? '—'}</td>
                        <td className="py-2 px-4 tabular-nums" style={{ color: 'var(--foreground)' }}>
                          {e.price != null ? formatPrice(e.price) : '—'}
                        </td>
                        <td className="py-2 px-4 tabular-nums" style={{ color: 'var(--foreground)' }}>
                          {amount != null ? formatCurrency(amount, { compact: true }) : '—'}
                        </td>
                        <td className="py-2 px-4 max-w-32 truncate" style={{ color: 'var(--muted-foreground)' }}>
                          {e.note || '—'}
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
                <p style={{ color: 'var(--muted-foreground)' }}>此分類無交易記錄</p>
              </div>
            )
          ) : (
            <div className="p-12 text-center">
              <p style={{ color: 'var(--muted-foreground)' }}>尚無交易記錄</p>
            </div>
          )}
          </div>
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
                    value={form.stock_id}
                    onChange={(e) => setForm(p => ({ ...p, stock_id: e.target.value.toUpperCase() }))}
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
                  {estimatedAmount} 元
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
                disabled={saving || !form.stock_id.trim()}
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

      {/* AI 交易行為回顧 */}
      <div className="mt-8">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-bold" style={{ color: 'var(--foreground)' }}>🤖 AI 交易行為回顧</h2>
          {data && data.entries.length > 0 && (
            <button
              onClick={handleAiReview}
              disabled={aiLoading}
              className="h-9 px-4 rounded-md text-sm font-medium disabled:opacity-60"
              style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}
            >
              {aiLoading ? '分析中...' : '🧠 產生 AI 回顧報告'}
            </button>
          )}
        </div>
        <div
          className="rounded-lg p-6 min-h-24"
          style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
        >
          {aiLoading ? (
            <div className="flex items-center gap-3">
              <div className="h-4 w-4 rounded-full border-2 border-t-transparent animate-spin" style={{ borderColor: 'var(--primary)', borderTopColor: 'transparent' }} />
              <span className="text-sm" style={{ color: 'var(--muted-foreground)' }}>AI 正在分析您的交易記錄...</span>
            </div>
          ) : aiReport ? (
            <div>
              <MarkdownReport>{aiReport}</MarkdownReport>
            </div>
          ) : data && data.entries.length === 0 ? (
            <p className="text-sm text-center" style={{ color: 'var(--muted-foreground)' }}>
              累積交易記錄後即可使用 AI 回顧功能
            </p>
          ) : (
            <p className="text-sm text-center" style={{ color: 'var(--muted-foreground)' }}>
              點擊「🧠 產生 AI 回顧報告」按鈕，讓 AI 分析您的交易行為模式
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
