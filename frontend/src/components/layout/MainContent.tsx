'use client'

import { useAppStore } from '@/store/useAppStore'
import { useQuotaStatus } from '@/lib/hooks/useQuotaStatus'
import { QUOTA_BANNER_HEIGHT } from '@/components/shared/QuotaBanner'

export function MainContent({ children }: { children: React.ReactNode }) {
  const { sidebarCollapsed, isMobile } = useAppStore()
  const { isExceeded } = useQuotaStatus()

  // 手機版：sidebar 以 overlay 方式呈現，不佔主內容空間
  const marginLeft = isMobile ? 0 : (sidebarCollapsed ? 60 : 260)

  return (
    <main
      className="min-h-screen transition-all duration-300"
      style={{
        marginLeft,
        paddingTop: 56 + (isExceeded ? QUOTA_BANNER_HEIGHT : 0),
      }}
    >
      {/* 手機版用較小的 padding */}
      <div className="p-3 md:p-6">{children}</div>
    </main>
  )
}
