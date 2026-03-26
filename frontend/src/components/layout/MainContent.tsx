'use client'

import { useAppStore } from '@/store/useAppStore'
import { useQuotaStatus } from '@/lib/hooks/useQuotaStatus'
import { QUOTA_BANNER_HEIGHT } from '@/components/shared/QuotaBanner'

export function MainContent({ children }: { children: React.ReactNode }) {
  const { sidebarCollapsed } = useAppStore()
  const { isExceeded } = useQuotaStatus()

  return (
    <main
      className="min-h-screen transition-all duration-300"
      style={{
        marginLeft: sidebarCollapsed ? 60 : 260,
        paddingTop: 56 + (isExceeded ? QUOTA_BANNER_HEIGHT : 0),
      }}
    >
      <div className="p-6">{children}</div>
    </main>
  )
}
