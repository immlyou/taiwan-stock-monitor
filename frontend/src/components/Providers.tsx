'use client'

import { useEffect } from 'react'
import { SWRConfig } from 'swr'
import { useAppStore } from '@/store/useAppStore'

function MobileDetector() {
  const { setIsMobile, setSidebarOpen } = useAppStore()

  useEffect(() => {
    const mq = window.matchMedia('(max-width: 767px)')

    const handleChange = (e: MediaQueryListEvent | MediaQueryList) => {
      const mobile = e.matches
      setIsMobile(mobile)
      // 手機版：sidebar 預設關閉
      if (mobile) {
        setSidebarOpen(false)
      }
    }

    // 初始偵測
    handleChange(mq)

    mq.addEventListener('change', handleChange)
    return () => mq.removeEventListener('change', handleChange)
  }, [setIsMobile, setSidebarOpen])

  return null
}

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <SWRConfig
      value={{
        dedupingInterval: 5000,
        revalidateOnFocus: false,
        errorRetryCount: 2,
        keepPreviousData: true,
      }}
    >
      <MobileDetector />
      {children}
    </SWRConfig>
  )
}
