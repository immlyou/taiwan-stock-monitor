'use client'

import { useState } from 'react'
import useSWR, { mutate } from 'swr'
import { fetchAPI } from '@/lib/api/client'
import { getChangeColorVar, formatPrice, formatVolume } from '@/lib/utils/format'

interface WatchlistItem {
  id: string
  code: string
  name: string
  close: number
  change: number
  changePercent: number
  open: number
  high: number
  low: number
  volume: number
  addedAt: string
}

const SWR_KEY = '/watchlists/default'

export default function WatchlistPage() {
  const { data: items, isLoading, error } = useSWR<WatchlistItem[]>(SWR_KEY, fetchAPI)
  const [addCode, setAddCode] = useState('')
  const [adding, setAdding] = useState(false)
  const [addError, setAddError] = useState('')

  const handleAdd = async () => {
    const code = addCode.trim().toUpperCase()
    if (!code) return
    setAdding(true)
    setAddError('')
    try {
      await fetchAPI(`${SWR_KEY}/stocks`, {
        method: 'POST',
        body: JSON.stringify({ code }),
      })
      await mutate(SWR_KEY)
      setAddCode('')
    } catch {
      setAddError(`新增 ${code} 失敗，請確認代號正確`)
    } finally {
      setAdding(false)
    }
  }

  const handleRemove = async (id: string) => {
    await fetchAPI(`${SWR_KEY}/stocks/${id}`, { method: 'DELETE' })
    await mutate(SWR_KEY)
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold" style={{ color: 'var(--foreground)' }}>自選股</h1>
        <p className="text-sm mt-1" style={{ color: 'var(--muted-foreground)' }}>追蹤關注的股票報價</p>
      </div>

      {/* 新增輸入 */}
      <div
        className="rounded-lg p-4 mb-6"
        style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
      >
        <div className="flex gap-2">
          <input
            type="text"
            value={addCode}
            onChange={(e) => setAddCode(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleAdd()}
            placeholder="輸入股票代號（例：2330）"
            className="flex-1 h-9 rounded-md border px-3 text-sm"
            style={{ background: 'var(--background)', border: '1px solid var(--border)', color: 'var(--foreground)' }}
          />
          <button
            onClick={handleAdd}
            disabled={adding || !addCode.trim()}
            className="h-9 px-4 rounded-md text-sm font-medium disabled:opacity-60"
            style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}
          >
            {adding ? '新增中...' : '新增自選'}
          </button>
        </div>
        {addError && (
          <p className="mt-2 text-xs" style={{ color: 'var(--destructive)' }}>{addError}</p>
        )}
      </div>

      {/* 自選股卡片 / 表格 */}
      {error ? (
        <div className="rounded-lg p-6 text-center" style={{ background: 'var(--card)', border: '1px solid var(--border)' }}>
          <p style={{ color: 'var(--destructive)' }}>資料載入失敗</p>
        </div>
      ) : isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="h-28 rounded-lg animate-pulse" style={{ background: 'var(--card)' }} />
          ))}
        </div>
      ) : items && items.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {items.map((item) => (
            <div
              key={item.id}
              className="rounded-lg p-4 relative"
              style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
            >
              {/* 移除按鈕 */}
              <button
                onClick={() => handleRemove(item.id)}
                className="absolute top-3 right-3 text-xs opacity-50 hover:opacity-100 transition-opacity"
                style={{ color: 'var(--muted-foreground)' }}
              >
                x
              </button>

              {/* 代號名稱 */}
              <div className="mb-2">
                <span className="font-semibold" style={{ color: 'var(--foreground)' }}>{item.code}</span>
                <span className="ml-2 text-sm" style={{ color: 'var(--muted-foreground)' }}>{item.name}</span>
              </div>

              {/* 價格 */}
              <div className="flex items-end gap-3 mb-2">
                <span className="text-2xl font-bold tabular-nums" style={{ color: 'var(--foreground)' }}>
                  {formatPrice(item.close)}
                </span>
                <span
                  className="text-sm font-semibold tabular-nums"
                  style={{ color: getChangeColorVar(item.change) }}
                >
                  {item.change > 0 ? '+' : ''}{formatPrice(item.change)}
                </span>
                <span
                  className="text-sm tabular-nums"
                  style={{ color: getChangeColorVar(item.changePercent) }}
                >
                  ({item.changePercent > 0 ? '+' : ''}{item.changePercent.toFixed(2)}%)
                </span>
              </div>

              {/* 今日行情 */}
              <div className="grid grid-cols-3 gap-1 text-xs">
                <div>
                  <span style={{ color: 'var(--muted-foreground)' }}>最高 </span>
                  <span style={{ color: 'var(--stock-up)' }}>{formatPrice(item.high)}</span>
                </div>
                <div>
                  <span style={{ color: 'var(--muted-foreground)' }}>最低 </span>
                  <span style={{ color: 'var(--stock-down)' }}>{formatPrice(item.low)}</span>
                </div>
                <div>
                  <span style={{ color: 'var(--muted-foreground)' }}>量 </span>
                  <span style={{ color: 'var(--foreground)' }}>{formatVolume(item.volume)}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div
          className="rounded-lg p-12 text-center"
          style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
        >
          <p className="text-lg mb-2" style={{ color: 'var(--muted-foreground)' }}>自選股清單為空</p>
          <p className="text-sm" style={{ color: 'var(--muted-foreground)' }}>
            在上方輸入股票代號，新增到自選股追蹤
          </p>
        </div>
      )}
    </div>
  )
}
