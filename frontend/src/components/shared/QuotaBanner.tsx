'use client'

import { useQuotaStatus } from '@/lib/hooks/useQuotaStatus'

export const QUOTA_BANNER_HEIGHT = 34

export function QuotaBanner() {
  const { isExceeded } = useQuotaStatus()

  if (!isExceeded) return null

  return (
    <div
      style={{
        height: QUOTA_BANNER_HEIGHT,
        background: '#92400e',
        color: '#fef3c7',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontSize: 13,
        flexShrink: 0,
      }}
    >
      ⚠️ 今日 FinLab API 資料額度已達上限（5,000 MB/日），資料將於午夜（UTC+8）自動重置恢復
    </div>
  )
}
