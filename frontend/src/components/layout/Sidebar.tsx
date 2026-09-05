'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
  ChevronDown, ChevronRight, Star, Settings, Compass, TrendingUp,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useAppStore } from '@/store/useAppStore'
import { useWatchlist } from '@/lib/hooks/useWatchlist'
import { getChangeColorVar } from '@/lib/utils/format'
import {
  NAVIGATION_GROUPS,
  isNavigationItemActive,
  type NavigationItem,
} from '@/lib/navigation/catalog'

const SYSTEM_ITEMS: NavigationItem[] = [
  { label: '系統設定', href: '/settings', icon: Settings, description: '通知、主題與系統資訊' },
]

/** 側欄持久自選股快捷：點代號直接前往個股分析（master-detail lite）。 */
function WatchlistNav({
  collapsed,
  onNavigate,
}: {
  collapsed: boolean
  onNavigate: () => void
}) {
  const { stocks } = useWatchlist()
  if (collapsed || stocks.length === 0) return null

  return (
    <div className="mt-2 pt-2" style={{ borderTop: '1px solid var(--border)' }}>
      <div
        className="flex items-center gap-1.5 px-3 py-1 text-xs font-semibold uppercase tracking-wider mb-1"
        style={{ color: 'var(--muted-foreground)' }}
      >
        <Star className="h-3.5 w-3.5" /> 自選股
      </div>
      {stocks.slice(0, 8).map((s) => {
        const pct = s.change_pct ?? 0
        return (
          <Link
            key={s.stock_id}
            href={`/stock/${s.stock_id}`}
            onClick={onNavigate}
            className="flex items-center justify-between gap-2 px-4 py-1.5 mx-1 rounded-md text-sm transition-colors hover:bg-secondary/50"
            style={{ color: 'var(--foreground)', minHeight: '36px' }}
          >
            <span className="flex items-center gap-2 min-w-0">
              <span className="num text-xs shrink-0" style={{ color: 'var(--primary)' }}>
                {s.stock_id}
              </span>
              <span className="truncate text-xs" style={{ color: 'var(--muted-foreground)' }}>
                {s.name}
              </span>
            </span>
            {s.change_pct != null && (
              <span className="num text-xs font-medium shrink-0" style={{ color: getChangeColorVar(pct) }}>
                {pct > 0 ? '▲' : pct < 0 ? '▼' : ''}{Math.abs(pct).toFixed(2)}%
              </span>
            )}
          </Link>
        )
      })}
    </div>
  )
}

export function Sidebar() {
  const pathname = usePathname()
  const {
    sidebarCollapsed,
    expandedGroups,
    toggleGroup,
    isMobile,
    sidebarOpen,
    setSidebarOpen,
  } = useAppStore()

  // 手機版：點擊連結後自動關閉 sidebar
  const handleLinkClick = () => {
    if (isMobile) {
      setSidebarOpen(false)
    }
  }

  // 手機版：sidebar 是否可見
  const mobileVisible = isMobile ? sidebarOpen : true

  // 導航連結（含 lucide 圖示），選中態用主題 accent-soft 底。
  const navLink = (item: NavigationItem) => {
    const isActive = isNavigationItemActive(item, pathname)
    const Icon = item.icon
    return (
      <Link
        key={item.href}
        href={item.href}
        onClick={handleLinkClick}
        className={cn(
          'flex items-center gap-2.5 px-4 py-1.5 mx-1 rounded-md text-sm transition-colors',
          isActive ? 'font-medium' : 'hover:bg-secondary/50'
        )}
        style={{
          color: isActive ? 'var(--primary)' : 'var(--foreground)',
          background: isActive ? 'var(--accent-soft)' : undefined,
          minHeight: '40px',
        }}
      >
        <Icon className="h-4 w-4 shrink-0" style={{ color: isActive ? 'var(--primary)' : 'var(--muted-foreground)' }} />
        {item.label}
      </Link>
    )
  }

  return (
    <>
      {/* 手機版遮罩 */}
      {isMobile && sidebarOpen && (
        <div
          onClick={() => setSidebarOpen(false)}
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 40,
            background: 'rgba(0,0,0,0.5)',
          }}
          aria-hidden="true"
        />
      )}

      <aside
        className={cn(
          'fixed left-0 top-0 h-full flex flex-col z-50 transition-all duration-300',
          'border-r overflow-hidden',
          // 桌面版寬度
          !isMobile && (sidebarCollapsed ? 'w-[60px]' : 'w-[260px]'),
          // 手機版固定 280px
          isMobile && 'w-[280px]',
        )}
        style={{
          background: 'var(--card)',
          borderColor: 'var(--border)',
          // 手機版：用 transform 滑入/滑出
          transform: isMobile
            ? (mobileVisible ? 'translateX(0)' : 'translateX(-100%)')
            : undefined,
          transition: 'transform 0.3s ease, width 0.3s',
        }}
      >
        {/* Logo 區域 */}
        <div
          className="flex items-center h-14 px-4 shrink-0 border-b"
          style={{ borderColor: 'var(--border)' }}
        >
          <div className="flex items-center gap-2 min-w-0">
            <TrendingUp className="h-5 w-5 shrink-0" style={{ color: 'var(--primary)' }} />
            {(!sidebarCollapsed || isMobile) && (
              <span
                className="font-bold text-sm whitespace-nowrap truncate"
                style={{ color: 'var(--foreground)', fontFamily: 'var(--font-serif)' }}
              >
                台股監控系統
              </span>
            )}
          </div>
        </div>

        {/* 導航區域 */}
        <nav className="flex-1 overflow-y-auto py-2">
          {/* 功能總覽捷徑 */}
          <Link
            href="/overview"
            onClick={handleLinkClick}
            className={cn('flex items-center gap-2.5 px-3 py-2 mx-1 mb-1 rounded-md text-sm font-medium transition-colors',
              pathname === '/overview' ? 'font-semibold' : 'hover:bg-secondary/50')}
            style={{
              color: pathname === '/overview' ? 'var(--primary)' : 'var(--foreground)',
              background: pathname === '/overview' ? 'var(--accent-soft)' : undefined,
              minHeight: '40px',
            }}
          >
            <Compass className="h-4 w-4 shrink-0" style={{ color: pathname === '/overview' ? 'var(--primary)' : 'var(--muted-foreground)' }} />
            {(!sidebarCollapsed || isMobile) && <span>功能總覽</span>}
          </Link>

          {NAVIGATION_GROUPS.map((group) => {
            const isExpanded = expandedGroups.includes(group.label)
            const GroupIcon = group.icon
            return (
              <div key={group.label} className="mb-1">
                {/* 群組標題 */}
                <button
                  onClick={() => toggleGroup(group.label)}
                  className={cn(
                    'w-full flex items-center gap-2 px-3 py-2 text-xs font-semibold transition-colors',
                    'hover:bg-secondary/50 rounded-md mx-1',
                    !isMobile && sidebarCollapsed && 'justify-center'
                  )}
                  style={{ color: 'var(--muted-foreground)', minHeight: '44px' }}
                >
                  <GroupIcon className="h-4 w-4 shrink-0" />
                  {(!sidebarCollapsed || isMobile) && (
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
                {(isExpanded || (!isMobile && sidebarCollapsed)) && (
                  <div className={cn((!isMobile && sidebarCollapsed) ? 'hidden' : 'block')}>
                    {group.items.map((item) => navLink(item))}
                  </div>
                )}
              </div>
            )
          })}

          {/* 持久自選股快捷 */}
          <WatchlistNav
            collapsed={!isMobile && sidebarCollapsed}
            onNavigate={handleLinkClick}
          />

          {/* 系統設定 */}
          <div className="mt-2 pt-2" style={{ borderTop: '1px solid var(--border)' }}>
            <div
              className={cn(
                'flex items-center gap-1.5 px-3 py-1 text-xs font-semibold uppercase tracking-wider mb-1',
                !isMobile && sidebarCollapsed && 'justify-center'
              )}
              style={{ color: 'var(--muted-foreground)' }}
            >
              <Settings className="h-3.5 w-3.5" />
              {(!sidebarCollapsed || isMobile) && '系統'}
            </div>
            {(!sidebarCollapsed || isMobile) && SYSTEM_ITEMS.map((item) => navLink(item))}
          </div>
        </nav>
      </aside>
    </>
  )
}
