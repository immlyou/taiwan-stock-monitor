import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type ThemeName = 'terminal' | 'editorial' | 'slate'
export type ModeName = 'dark' | 'light'

// 每套主題的代表模式：切換主題時連帶套上其招牌深淺。
export const THEME_DEFAULT_MODE: Record<ThemeName, ModeName> = {
  terminal: 'dark',
  editorial: 'light',
  slate: 'dark',
}

function readInitialTheme(): ThemeName {
  if (typeof document !== 'undefined') {
    const t = document.documentElement.dataset.theme
    if (t === 'terminal' || t === 'editorial' || t === 'slate') return t
  }
  return 'terminal'
}

function readInitialMode(theme: ThemeName): ModeName {
  if (typeof document !== 'undefined') {
    const m = document.documentElement.dataset.mode
    if (m === 'dark' || m === 'light') return m
  }
  return THEME_DEFAULT_MODE[theme]
}

// 套用主題到 <html> 並寫入 localStorage（與 layout 的 no-flash script 同一組 key）。
function applyTheme(theme: ThemeName, mode: ModeName): void {
  if (typeof document !== 'undefined') {
    document.documentElement.dataset.theme = theme
    document.documentElement.dataset.mode = mode
  }
  try {
    localStorage.setItem('tw_theme', theme)
    localStorage.setItem('tw_mode', mode)
  } catch {
    /* localStorage 不可用時靜默略過 */
  }
}

interface AppState {
  // 佈景主題與深淺模式
  theme: ThemeName
  mode: ModeName
  setTheme: (theme: ThemeName) => void
  setMode: (mode: ModeName) => void

  // 側邊欄摺疊（桌面版）
  sidebarCollapsed: boolean
  toggleSidebar: () => void
  setSidebarCollapsed: (collapsed: boolean) => void

  // 手機版 sidebar 開關
  sidebarOpen: boolean
  setSidebarOpen: (open: boolean) => void
  toggleMobileSidebar: () => void

  // 手機偵測
  isMobile: boolean
  setIsMobile: (mobile: boolean) => void

  // 展開的群組
  expandedGroups: string[]
  toggleGroup: (group: string) => void
  setGroupExpanded: (group: string, expanded: boolean) => void

  // 目前選擇的股票
  activeStockCode: string | null
  setActiveStockCode: (code: string | null) => void

  // 資料日期
  dataDate: string | null
  setDataDate: (date: string | null) => void
}

export const useAppStore = create<AppState>()(
  persist(
    (set, get) => ({
      // 佈景主題（初始值讀自 <html> dataset，由 no-flash script 在 paint 前設好）
      theme: readInitialTheme(),
      mode: readInitialMode(readInitialTheme()),
      setTheme: (theme) => {
        const mode = THEME_DEFAULT_MODE[theme]
        applyTheme(theme, mode)
        set({ theme, mode })
      },
      setMode: (mode) => {
        applyTheme(get().theme, mode)
        set({ mode })
      },

      // 側邊欄（桌面版摺疊）
      sidebarCollapsed: false,
      toggleSidebar: () =>
        set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
      setSidebarCollapsed: (collapsed) =>
        set({ sidebarCollapsed: collapsed }),

      // 手機版 sidebar
      sidebarOpen: false,
      setSidebarOpen: (open) => set({ sidebarOpen: open }),
      toggleMobileSidebar: () =>
        set((state) => ({ sidebarOpen: !state.sidebarOpen })),

      // 手機偵測（初始值 false，由 layout 的 useEffect 更新）
      isMobile: false,
      setIsMobile: (mobile) => set({ isMobile: mobile }),

      // 展開的群組（預設展開所有群組）
      expandedGroups: ['市場動態', '研究分析', '選股策略', '投資管理'],
      toggleGroup: (group) =>
        set((state) => ({
          expandedGroups: state.expandedGroups.includes(group)
            ? state.expandedGroups.filter((g) => g !== group)
            : [...state.expandedGroups, group],
        })),
      setGroupExpanded: (group, expanded) =>
        set((state) => ({
          expandedGroups: expanded
            ? [...state.expandedGroups, group]
            : state.expandedGroups.filter((g) => g !== group),
        })),

      // 目前股票
      activeStockCode: null,
      setActiveStockCode: (code) => set({ activeStockCode: code }),

      // 資料日期
      dataDate: null,
      setDataDate: (date) => set({ dataDate: date }),
    }),
    {
      name: 'taiwan-stock-monitor',
      partialize: (state) => ({
        sidebarCollapsed: state.sidebarCollapsed,
        expandedGroups: state.expandedGroups,
      }),
    }
  )
)
