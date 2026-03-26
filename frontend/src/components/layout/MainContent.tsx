'use client'

import { useAppStore } from '@/store/useAppStore'

export function MainContent({ children }: { children: React.ReactNode }) {
  const { sidebarCollapsed } = useAppStore()

  return (
    <main
      className="min-h-screen pt-14 transition-all duration-300"
      style={{
        marginLeft: sidebarCollapsed ? 60 : 260,
      }}
    >
      <div className="p-6">{children}</div>
    </main>
  )
}
