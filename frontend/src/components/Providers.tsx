'use client'

import { useEffect, useMemo, useSyncExternalStore } from 'react'
import { SWRConfig } from 'swr'
import type { Cache, State } from 'swr'
import { SessionProvider, useSession } from 'next-auth/react'
import { useAppStore } from '@/store/useAppStore'

// 僅在 client 為 true 的旗標（hydration-safe，不用 setState-in-effect）。
const emptySubscribe = () => () => {}
function useMounted(): boolean {
  return useSyncExternalStore(emptySubscribe, () => true, () => false)
}

// 版本字串：回應結構改變（例如新增欄位）時 bump，讓所有舊快取自動失效一次，
// 避免使用者看到缺欄位的舊資料（如 XGBoost 排行缺 price → 顯示「—」）。
const LEGACY_SWR_CACHE_KEY = 'swr-cache-v2'
const SWR_CACHE_PREFIX = 'swr-cache-v3:'

/**
 * localStorage 後端的 SWR cache provider —— 讓資料跨「重新整理」保留。
 *
 * 啟動時 hydrate 上次的資料 → 頁面立刻顯示舊資料 → SWR 背景 revalidate
 * → 新資料到了再換（stale-while-revalidate）。純記憶體快取在 reload 會清空，
 * 所以每次重整都得從骨架開始；持久化後就能「先看舊的、好了換新的」。
 *
 * 只持久化「有 data、無 error」的項目，避免把載入中/錯誤狀態（如暫時 503）
 * 也存進去、下次啟動誤顯示錯誤。寫入以 try/catch 包住，quota 爆掉就略過。
 */
function localStorageProvider(storageKey: string): Cache {
  const map = new Map<string, State<unknown>>()

  if (typeof window === 'undefined') {
    return map as unknown as Cache
  }

  try {
    // v2 未分帳號，不能安全沿用；首次建立任一帳號 cache 時直接淘汰。
    localStorage.removeItem(LEGACY_SWR_CACHE_KEY)
    const saved = localStorage.getItem(storageKey)
    if (saved) {
      for (const [key, value] of JSON.parse(saved) as [string, State<unknown>][]) {
        map.set(key, value)
      }
    }
  } catch {
    // 壞資料 / 解析失敗：視為空快取
  }

  const persist = () => {
    try {
      const entries: [string, State<unknown>][] = []
      for (const [key, value] of map.entries()) {
        // 只存成功取得的資料；丟掉 error / isLoading 等暫態
        if (value && value.data !== undefined && !value.error) {
          entries.push([key, { data: value.data } as State<unknown>])
        }
      }
      localStorage.setItem(storageKey, JSON.stringify(entries))
    } catch {
      // localStorage quota 爆掉或序列化失敗：略過持久化，退回純記憶體
    }
  }

  window.addEventListener('beforeunload', persist)
  // 行動裝置 beforeunload 不可靠，分頁切到背景時也存一次
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') persist()
  })

  return map as unknown as Cache
}

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

// 空快取 provider：與伺服器端（無 localStorage）行為一致。
// 首次 client render 必須用它，避免 SSR（空快取→骨架）與 client（已從
// localStorage 預載資料→實際內容）渲染結果不同而觸發 hydration mismatch
// （React #418）。掛載後再切換到 localStorageProvider，享用持久化快取。
function emptyProvider(): Cache {
  return new Map<string, State<unknown>>() as unknown as Cache
}

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <SessionProvider>
      <UserScopedSWRProvider>{children}</UserScopedSWRProvider>
    </SessionProvider>
  )
}

function UserScopedSWRProvider({ children }: { children: React.ReactNode }) {
  const mounted = useMounted()
  const { data: session, status } = useSession()
  const userId = session?.user?.id
  const storageKey = mounted && status === 'authenticated' && userId
    ? `${SWR_CACHE_PREFIX}${userId}`
    : null
  const provider = useMemo(
    () => storageKey
      ? () => localStorageProvider(storageKey)
      : emptyProvider,
    [storageKey]
  )

  return (
    <SWRConfig
      key={storageKey ?? `session-${status}`}
      value={{
        provider,
        dedupingInterval: 5000,
        revalidateOnFocus: false,
        // fetchAPI 已針對暫時性 GET 錯誤做一次重試；避免 SWR 再疊加成 retry storm。
        errorRetryCount: 0,
        keepPreviousData: true,
      }}
    >
      <MobileDetector />
      {children}
    </SWRConfig>
  )
}
