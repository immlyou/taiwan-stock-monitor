'use client'

import { useState } from 'react'
import { fetchAPI } from '@/lib/api/client'

export interface ImportedHolding {
  stock_id: string
  name: string
  shares: number
  cost_price: number
}

interface Props {
  open: boolean
  onClose: () => void
  /** holdings: 可編輯股數/成本的表格；codes: 只顯示代號 chips */
  mode: 'holdings' | 'codes'
  title?: string
  /** 批次確認（投組/自選股）：回傳目前清單 */
  onConfirm?: (items: ImportedHolding[]) => void | Promise<void>
  confirmLabel?: string
  /** 單選（個股分析）：點某一檔代號即觸發（如跳轉分析） */
  onPickOne?: (stockId: string) => void
}

const inputStyle = { background: 'var(--secondary)', color: 'var(--foreground)', border: '1px solid var(--border)' }

export function ScreenshotImportDialog({ open, onClose, mode, title, onConfirm, confirmLabel, onPickOne }: Props) {
  const [items, setItems] = useState<ImportedHolding[]>([])
  const [extracting, setExtracting] = useState(false)
  const [error, setError] = useState('')
  const [confirming, setConfirming] = useState(false)

  if (!open) return null

  async function handleFiles(files: FileList) {
    setExtracting(true); setError('')
    try {
      const merged = [...items]
      for (const file of Array.from(files)) {
        const dataUrl: string = await new Promise((resolve, reject) => {
          const r = new FileReader()
          r.onload = () => resolve(r.result as string)
          r.onerror = () => reject(new Error('讀取檔案失敗'))
          r.readAsDataURL(file)
        })
        const comma = dataUrl.indexOf(',')
        const base64 = dataUrl.slice(comma + 1)
        const mediaType = dataUrl.slice(5, comma).split(';')[0] || 'image/png'
        const res = await fetchAPI<{ holdings: ImportedHolding[] }>('/advisor/extract-holdings', {
          method: 'POST', body: JSON.stringify({ image_base64: base64, media_type: mediaType }),
        }, 60000)
        for (const h of res.holdings ?? []) {
          const idx = merged.findIndex((m) => m.stock_id === h.stock_id)
          if (idx >= 0) merged[idx] = { ...merged[idx], shares: merged[idx].shares + h.shares }
          else merged.push(h)
        }
      }
      setItems(merged)
      if (!merged.length) setError('沒辨識出股票，請換清晰一點的截圖')
    } catch (e) {
      setError(e instanceof Error ? e.message : '辨識失敗，請稍後再試')
    } finally {
      setExtracting(false)
    }
  }

  function update(i: number, field: 'shares' | 'cost_price', v: string) {
    setItems((p) => p.map((h, idx) => idx === i ? { ...h, [field]: Number(v) || 0 } : h))
  }
  function remove(i: number) { setItems((p) => p.filter((_, idx) => idx !== i)) }

  async function confirm() {
    if (!onConfirm || !items.length) return
    setConfirming(true)
    try { await onConfirm(items); reset(); onClose() }
    catch (e) { setError(e instanceof Error ? e.message : '匯入失敗') }
    finally { setConfirming(false) }
  }
  function reset() { setItems([]); setError('') }
  function close() { reset(); onClose() }

  return (
    <div role="dialog" aria-modal="true" aria-label={title || '截圖匯入'}
      onKeyDown={(e) => { if (e.key === 'Escape') close() }}
      style={{ position: 'fixed', inset: 0, zIndex: 60, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(0,0,0,0.6)' }}>
      <div onClick={(e) => e.stopPropagation()} className="w-[92vw] max-w-lg max-h-[85vh] overflow-y-auto rounded-lg p-5"
        style={{ background: 'var(--card)', border: '1px solid var(--border)' }}>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-base font-semibold" style={{ color: 'var(--foreground)' }}>{title || '📷 截圖匯入'}</h2>
          <button onClick={close} aria-label="關閉" className="text-sm" style={{ color: 'var(--muted-foreground)' }}>✕</button>
        </div>

        <input type="file" accept="image/png,image/jpeg,image/webp" multiple disabled={extracting}
          onChange={(e) => { if (e.target.files?.length) handleFiles(e.target.files); e.target.value = '' }}
          className="block w-full text-sm mb-2" style={{ color: 'var(--foreground)' }} />
        <p className="text-xs mb-2" style={{ color: 'var(--muted-foreground)' }}>可上傳一或多張券商持股截圖，AI 自動辨識（不消耗 FinLab 額度）。</p>
        {extracting && <p className="text-sm" style={{ color: 'var(--primary)' }}>🔍 AI 辨識中…</p>}
        {error && <p className="text-sm" style={{ color: 'var(--stock-up)' }}>{error}</p>}

        {items.length > 0 && mode === 'holdings' && (
          <div className="rounded-md overflow-hidden mt-2" style={{ border: '1px solid var(--border)' }}>
            <div className="grid grid-cols-[1fr_80px_80px_28px] gap-2 px-2 py-1.5 text-xs" style={{ background: 'var(--secondary)', color: 'var(--muted-foreground)' }}>
              <span>代號/名稱</span><span className="text-right">股數</span><span className="text-right">成本</span><span></span>
            </div>
            {items.map((h, i) => (
              <div key={`${h.stock_id}-${i}`} className="grid grid-cols-[1fr_80px_80px_28px] gap-2 px-2 py-1.5 items-center" style={{ borderTop: '1px solid var(--border)' }}>
                <span className="text-sm truncate"><span className="font-mono" style={{ color: 'var(--primary)' }}>{h.stock_id}</span> <span style={{ color: 'var(--muted-foreground)' }}>{h.name}</span></span>
                <input type="number" min="0" value={h.shares} onChange={(e) => update(i, 'shares', e.target.value)} className="h-8 px-2 rounded text-sm text-right num" style={inputStyle} />
                <input type="number" min="0" value={h.cost_price} onChange={(e) => update(i, 'cost_price', e.target.value)} className="h-8 px-2 rounded text-sm text-right num" style={inputStyle} />
                <button onClick={() => remove(i)} aria-label="移除" style={{ color: 'var(--muted-foreground)' }}>✕</button>
              </div>
            ))}
          </div>
        )}

        {items.length > 0 && mode === 'codes' && (
          <div className="flex flex-wrap gap-2 mt-2">
            {items.map((h, i) => (
              <button key={`${h.stock_id}-${i}`}
                onClick={() => { if (onPickOne) { onPickOne(h.stock_id); close() } }}
                className="px-2.5 py-1 rounded-full text-sm flex items-center gap-1.5"
                style={{ background: 'var(--secondary)', border: '1px solid var(--border)', color: 'var(--foreground)', cursor: onPickOne ? 'pointer' : 'default' }}>
                <span className="font-mono" style={{ color: 'var(--primary)' }}>{h.stock_id}</span>
                <span style={{ color: 'var(--muted-foreground)' }}>{h.name}</span>
                {!onPickOne && <span onClick={(e) => { e.stopPropagation(); remove(i) }} aria-label="移除" style={{ color: 'var(--muted-foreground)' }}>✕</span>}
              </button>
            ))}
          </div>
        )}

        {onConfirm && items.length > 0 && (
          <div className="flex justify-end gap-2 mt-4">
            <button onClick={close} className="px-4 h-9 rounded-md text-sm" style={{ background: 'var(--secondary)', color: 'var(--foreground)', border: '1px solid var(--border)' }}>取消</button>
            <button onClick={confirm} disabled={confirming} className="px-4 h-9 rounded-md text-sm font-medium disabled:opacity-50" style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}>
              {confirming ? '匯入中…' : (confirmLabel || `確認匯入 ${items.length} 檔`)}
            </button>
          </div>
        )}
        {onPickOne && items.length > 0 && (
          <p className="text-xs mt-3" style={{ color: 'var(--muted-foreground)' }}>點選股票即前往其個股分析。</p>
        )}
      </div>
    </div>
  )
}
