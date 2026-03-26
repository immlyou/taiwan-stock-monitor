import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface AppState {
  // 側邊欄狀態
  sidebarCollapsed: boolean
  toggleSidebar: () => void
  setSidebarCollapsed: (collapsed: boolean) => void

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
    (set) => ({
      // 側邊欄
      sidebarCollapsed: false,
      toggleSidebar: () =>
        set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
      setSidebarCollapsed: (collapsed) =>
        set({ sidebarCollapsed: collapsed }),

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
