'use client'

import { usePathname } from 'next/navigation'
import Link from 'next/link'
import { useAccount } from '@/lib/hooks/useAccount'
import { ApiError } from '@/lib/api/client'

import { Header } from '@/components/layout/Header'
import { MainContent } from '@/components/layout/MainContent'
import { Sidebar } from '@/components/layout/Sidebar'

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const { data: account, error } = useAccount()

  if (pathname === '/login') return children
  if (error instanceof ApiError && error.status === 403) {
    return <main className="min-h-screen flex flex-col items-center justify-center gap-4 p-6">
      <h1 className="text-xl font-semibold">帳號未獲授權或已停用</h1>
      <p>請聯絡管理員，或切換至已受邀的 Google 帳號。</p>
      <Link className="underline" href="/login">切換帳號</Link>
    </main>
  }

  return (
    <>
      <Sidebar />
      <Header />
      <MainContent>
        {!error && account?.role === 'viewer' && <p role="status" className="mb-4 rounded-md border border-border p-3 text-sm">
          目前為唯讀帳號：可查看行情與個人資料，不能儲存修改、發送通知或執行需提交的分析。
        </p>}
        {children}
      </MainContent>
    </>
  )
}
