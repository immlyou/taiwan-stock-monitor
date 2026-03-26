'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useAppStore } from '@/store/useAppStore'

interface NavItem {
  label: string
  href: string
}

interface NavGroup {
  label: string
  icon: string
  items: NavItem[]
}

const NAV_GROUPS: NavGroup[] = [
  {
    label: '市場動態',
    icon: '📡',
    items: [
      { label: '持倉總覽', href: '/dashboard' },
      { label: '即時報價', href: '/realtime' },
      { label: '每日晨報', href: '/morning-report' },
      { label: '市場熱力圖', href: '/heatmap' },
      { label: '資金流向', href: '/money-flow' },
      { label: '盤後總覽', href: '/after-hours' },
    ],
  },
  {
    label: '研究分析',
    icon: '🔬',
    items: [
      { label: '個股分析', href: '/stock/2330' },
      { label: '技術分析', href: '/technical' },
      { label: '比較分析', href: '/compare' },
      { label: '產業分析', href: '/industry' },
      { label: '籌碼分析', href: '/chip' },
      { label: '財報分析', href: '/financials' },
      { label: '風險分析', href: '/risk' },
    ],
  },
  {
    label: '選股策略',
    icon: '🎯',
    items: [
      { label: '選股篩選', href: '/screener' },
      { label: 'AI 智慧選股', href: '/ai-pick' },
      { label: '回測分析', href: '/backtest' },
      { label: '策略管理', href: '/strategies' },
      { label: '參數優化', href: '/optimizer' },
      { label: '預測驗證', href: '/predictions' },
    ],
  },
  {
    label: '投資管理',
    icon: '💼',
    items: [
      { label: '投資組合', href: '/portfolio' },
      { label: '自選股', href: '/watchlist' },
      { label: '交易日誌', href: '/journal' },
      { label: '警報設定', href: '/alerts' },
    ],
  },
]

const SYSTEM_ITEMS: NavItem[] = [
  { label: '系統設定', href: '/settings' },
]

export function Sidebar() {
  const pathname = usePathname()
  const { sidebarCollapsed, expandedGroups, toggleGroup } = useAppStore()

  return (
    <aside
      className={cn(
        'fixed left-0 top-0 h-full flex flex-col z-30 transition-all duration-300',
        'border-r overflow-hidden',
        sidebarCollapsed
          ? 'w-[60px]'
          : 'w-[260px]'
      )}
      style={{ background: 'var(--card)', borderColor: 'var(--border)' }}
    >
      {/* Logo 區域 */}
      <div
        className="flex items-center h-14 px-4 shrink-0 border-b"
        style={{ borderColor: 'var(--border)' }}
      >
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-xl shrink-0">📈</span>
          {!sidebarCollapsed && (
            <span className="font-bold text-sm whitespace-nowrap truncate" style={{ color: 'var(--foreground)' }}>
              台股監控系統
            </span>
          )}
        </div>
      </div>

      {/* 導航區域 */}
      <nav className="flex-1 overflow-y-auto py-2">
        {NAV_GROUPS.map((group) => {
          const isExpanded = expandedGroups.includes(group.label)
          return (
            <div key={group.label} className="mb-1">
              {/* 群組標題 */}
              <button
                onClick={() => toggleGroup(group.label)}
                className={cn(
                  'w-full flex items-center gap-2 px-3 py-2 text-xs font-semibold transition-colors',
                  'hover:bg-secondary/50 rounded-md mx-1',
                  sidebarCollapsed && 'justify-center'
                )}
                style={{ color: 'var(--muted-foreground)' }}
              >
                <span className="text-base">{group.icon}</span>
                {!sidebarCollapsed && (
                  <>
                    <span className="flex-1 text-left uppercase tracking-wider">
                      {group.label}
                    </span>
                    {isExpanded ? (
                      <ChevronDown className="h-3 w-3" />
                    ) : (
                      <ChevronRight className="h-3 w-3" />
                    )}
                  </>
                )}
              </button>

              {/* 群組項目 */}
              {(isExpanded || sidebarCollapsed) && (
                <div className={cn(sidebarCollapsed ? 'hidden' : 'block')}>
                  {group.items.map((item) => {
                    const isActive = pathname === item.href
                    return (
                      <Link
                        key={item.href}
                        href={item.href}
                        className={cn(
                          'flex items-center gap-2 px-4 py-1.5 mx-1 rounded-md text-sm transition-colors',
                          isActive
                            ? 'font-medium'
                            : 'hover:bg-secondary/50'
                        )}
                        style={{
                          color: isActive ? 'var(--primary)' : 'var(--foreground)',
                          background: isActive ? 'rgba(59,130,246,0.12)' : undefined,
                        }}
                      >
                        {item.label}
                      </Link>
                    )
                  })}
                </div>
              )}
            </div>
          )
        })}

        {/* 系統設定 */}
        <div className="mt-2 pt-2" style={{ borderTop: '1px solid var(--border)' }}>
          <div
            className={cn(
              'px-3 py-1 text-xs font-semibold uppercase tracking-wider mb-1',
              sidebarCollapsed && 'text-center'
            )}
            style={{ color: 'var(--muted-foreground)' }}
          >
            {!sidebarCollapsed && '⚙️ 系統'}
            {sidebarCollapsed && '⚙️'}
          </div>
          {!sidebarCollapsed &&
            SYSTEM_ITEMS.map((item) => {
              const isActive = pathname === item.href
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    'flex items-center gap-2 px-4 py-1.5 mx-1 rounded-md text-sm transition-colors',
                    isActive ? 'font-medium' : 'hover:bg-secondary/50'
                  )}
                  style={{
                    color: isActive ? 'var(--primary)' : 'var(--foreground)',
                    background: isActive ? 'rgba(59,130,246,0.12)' : undefined,
                  }}
                >
                  {item.label}
                </Link>
              )
            })}
        </div>
      </nav>
    </aside>
  )
}
