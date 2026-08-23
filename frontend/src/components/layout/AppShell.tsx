'use client'

import { usePathname } from 'next/navigation'

import { Header } from '@/components/layout/Header'
import { MainContent } from '@/components/layout/MainContent'
import { Sidebar } from '@/components/layout/Sidebar'

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()

  if (pathname === '/login') return children

  return (
    <>
      <Sidebar />
      <Header />
      <MainContent>{children}</MainContent>
    </>
  )
}
