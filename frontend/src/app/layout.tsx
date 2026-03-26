import type { Metadata } from 'next'
import { Geist, Geist_Mono } from 'next/font/google'
import './globals.css'
import { Sidebar } from '@/components/layout/Sidebar'
import { Header } from '@/components/layout/Header'
import { MainContent } from '@/components/layout/MainContent'
import { Providers } from '@/components/Providers'

const geistSans = Geist({
  variable: '--font-geist-sans',
  subsets: ['latin'],
  display: 'swap',
})

const geistMono = Geist_Mono({
  variable: '--font-geist-mono',
  subsets: ['latin'],
  display: 'swap',
})

export const metadata: Metadata = {
  title: '台股監控系統',
  description: '台灣股票市場即時監控與分析平台',
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html
      lang="zh-TW"
      className={`${geistSans.variable} ${geistMono.variable} h-full`}
    >
      <body className="h-full" style={{ background: 'var(--background)', color: 'var(--foreground)' }}>
        <Providers>
          <Sidebar />
          <Header />
          <MainContent>{children}</MainContent>
        </Providers>
      </body>
    </html>
  )
}
