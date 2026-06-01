'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { RefreshCw, Check, AlertCircle } from 'lucide-react'
import { useSWRConfig } from 'swr'
import { systemApi, QuotaExceededError, ApiError } from '@/lib/api/client'
import { useAppStore } from '@/store/useAppStore'

type Status = 'idle' | 'loading' | 'success' | 'error'

export function RefreshDataButton() {
  const setDataDate = useAppStore((s) => s.setDataDate)
  const isMobile = useAppStore((s) => s.isMobile)
  const { mutate } = useSWRConfig()

  const [status, setStatus] = useState<Status>('idle')
  const [message, setMessage] = useState<string>('')
  const resetTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    return () => {
      if (resetTimer.current) clearTimeout(resetTimer.current)
    }
  }, [])

  const scheduleReset = useCallback((delay: number) => {
    if (resetTimer.current) clearTimeout(resetTimer.current)
    resetTimer.current = setTimeout(() => {
      setStatus('idle')
      setMessage('')
    }, delay)
  }, [])

  const handleRefresh = useCallback(async () => {
    if (status === 'loading') return
    setStatus('loading')
    setMessage('')
    try {
      const result = await systemApi.refresh()
      if (result.latest_data_date) {
        setDataDate(result.latest_data_date)
      }
      // 讓 /health 等依賴資料新鮮度的查詢重新抓取
      mutate('/health')
      if (result.failed.length > 0) {
        setStatus('error')
        setMessage(`部分資料更新失敗：${result.failed.join('、')}`)
        scheduleReset(6000)
      } else {
        setStatus('success')
        setMessage(
          result.latest_data_date
            ? `已更新至 ${result.latest_data_date}`
            : '資料已更新'
        )
        scheduleReset(4000)
      }
    } catch (err) {
      setStatus('error')
      if (err instanceof QuotaExceededError) {
        setMessage('FinLab 額度已達上限，午夜後自動恢復')
      } else if (err instanceof ApiError && err.status === 409) {
        setMessage('更新進行中，請稍候')
      } else {
        setMessage('更新失敗，請稍後再試')
      }
      scheduleReset(6000)
    }
  }, [status, setDataDate, mutate, scheduleReset])

  const isLoading = status === 'loading'

  const Icon =
    status === 'success' ? Check : status === 'error' ? AlertCircle : RefreshCw

  // 成功用綠色、失敗用紅色（不沿用台股漲跌色，避免成功/失敗同為紅色而混淆）
  const iconColor =
    status === 'success'
      ? '#16a34a'
      : status === 'error'
        ? '#dc2626'
        : 'var(--muted-foreground)'

  return (
    <div className="relative flex items-center">
      <button
        onClick={handleRefresh}
        disabled={isLoading}
        className="p-2 rounded-md transition-colors hover:bg-secondary/50 disabled:cursor-not-allowed disabled:opacity-70 shrink-0"
        style={{
          minWidth: 40,
          minHeight: 40,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
        aria-label="更新最新股票資料"
        title={isLoading ? '資料更新中…' : message || '更新最新股票資料'}
        aria-busy={isLoading}
      >
        <Icon
          className={`h-5 w-5 ${isLoading ? 'animate-spin' : ''}`}
          style={{ color: iconColor }}
        />
      </button>

      {/* 結果提示：桌面版以浮動小卡呈現，手機版省略避免擋住版面 */}
      {!isMobile && message && status !== 'loading' && (
        <div
          role="status"
          className="absolute right-0 top-full mt-1 whitespace-nowrap rounded-md px-2.5 py-1 text-xs shadow-md z-30"
          style={{
            background: 'var(--card)',
            color: status === 'error' ? '#dc2626' : 'var(--foreground)',
            border: '1px solid var(--border)',
          }}
        >
          {message}
        </div>
      )}
    </div>
  )
}
