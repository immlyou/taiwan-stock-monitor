'use client'

import { PanelLeftClose, PanelLeftOpen } from 'lucide-react'
import { useAppStore } from '@/store/useAppStore'
import { StockSearch } from '@/components/shared/StockSearch'
import { QuotaBanner } from '@/components/shared/QuotaBanner'

export function Header() {
  const { sidebarCollapsed, toggleSidebar, dataDate } = useAppStore()

  return (
    <header
      className="fixed top-0 right-0 z-20 flex flex-col border-b"
      style={{
        left: sidebarCollapsed ? 60 : 260,
        background: 'var(--card)',
        borderColor: 'var(--border)',
        transition: 'left 0.3s',
      }}
    >
      <QuotaBanner />
      {/* 主列 */}
      <div className="flex items-center gap-4 px-4 h-14">
        {/* 側邊欄切換按鈕 */}
        <button
          onClick={toggleSidebar}
          className="p-1.5 rounded-md transition-colors hover:bg-secondary/50"
          aria-label={sidebarCollapsed ? '展開側邊欄' : '收合側邊欄'}
        >
          {sidebarCollapsed ? (
            <PanelLeftOpen className="h-5 w-5" style={{ color: 'var(--muted-foreground)' }} />
          ) : (
            <PanelLeftClose className="h-5 w-5" style={{ color: 'var(--muted-foreground)' }} />
          )}
        </button>

        {/* 股票搜尋框 */}
        <div className="flex-1 max-w-md">
          <StockSearch />
        </div>

        {/* 右側區域 */}
        <div className="ml-auto flex items-center gap-4">
          {/* 資料日期 */}
          {dataDate && (
            <div className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
              資料日期：
              <span className="font-medium" style={{ color: 'var(--foreground)' }}>
                {dataDate}
              </span>
            </div>
          )}

          {/* 系統狀態指示燈 */}
          <div className="flex items-center gap-1.5">
            <div
              className="h-2 w-2 rounded-full animate-pulse"
              style={{ background: 'var(--stock-down)' }}
            />
            <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
              即時
            </span>
          </div>
        </div>
      </div>
    </header>
  )
}
