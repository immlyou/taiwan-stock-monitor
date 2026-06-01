'use client'

import { Menu, PanelLeftClose, PanelLeftOpen } from 'lucide-react'
import { useAppStore } from '@/store/useAppStore'
import { StockSearch } from '@/components/shared/StockSearch'
import { QuotaBanner } from '@/components/shared/QuotaBanner'
import { RefreshDataButton } from '@/components/shared/RefreshDataButton'
import { MarketTicker } from '@/components/layout/MarketTicker'

export function Header() {
  const {
    sidebarCollapsed,
    toggleSidebar,
    dataDate,
    isMobile,
    toggleMobileSidebar,
  } = useAppStore()

  // 桌面版：依 sidebarCollapsed 決定 left；手機版：left = 0
  const leftOffset = isMobile ? 0 : (sidebarCollapsed ? 60 : 260)

  return (
    <header
      className="fixed top-0 right-0 z-20 flex flex-col border-b"
      style={{
        left: leftOffset,
        background: 'var(--card)',
        borderColor: 'var(--border)',
        transition: 'left 0.3s',
      }}
    >
      <MarketTicker />
      <QuotaBanner />
      {/* 主列 */}
      <div className="flex items-center gap-2 md:gap-4 px-3 md:px-4 h-14">

        {/* 手機版：漢堡按鈕 */}
        {isMobile ? (
          <button
            onClick={toggleMobileSidebar}
            className="p-2 rounded-md transition-colors hover:bg-secondary/50 shrink-0"
            aria-label="開啟選單"
            style={{ minWidth: '44px', minHeight: '44px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
          >
            <Menu className="h-5 w-5" style={{ color: 'var(--muted-foreground)' }} />
          </button>
        ) : (
          /* 桌面版：側邊欄切換按鈕 */
          <button
            onClick={toggleSidebar}
            className="p-1.5 rounded-md transition-colors hover:bg-secondary/50 shrink-0"
            aria-label={sidebarCollapsed ? '展開側邊欄' : '收合側邊欄'}
          >
            {sidebarCollapsed ? (
              <PanelLeftOpen className="h-5 w-5" style={{ color: 'var(--muted-foreground)' }} />
            ) : (
              <PanelLeftClose className="h-5 w-5" style={{ color: 'var(--muted-foreground)' }} />
            )}
          </button>
        )}

        {/* 股票搜尋框：手機版縮短 */}
        <div className={isMobile ? 'flex-1 min-w-0' : 'flex-1 max-w-md'}>
          <StockSearch />
        </div>

        {/* 右側區域 */}
        <div className="ml-auto flex items-center gap-2 md:gap-4 shrink-0">
          {/* 強制手動更新最新股票資料 */}
          <RefreshDataButton />

          {/* 資料日期：手機版隱藏 */}
          {dataDate && !isMobile && (
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
            {!isMobile && (
              <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
                即時
              </span>
            )}
          </div>
        </div>
      </div>
    </header>
  )
}
