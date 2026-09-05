'use client'

import useSWR from 'swr'
import { fetchAPI } from '@/lib/api/client'
import { parseSettingsResponse } from '@/lib/contracts/settings'

/** User preference is a minimum: market-closed and provider rate limits win. */
export function useRefreshInterval() {
  const { data } = useSWR('/settings', async (path: string) =>
    parseSettingsResponse(await fetchAPI(path)))
  const seconds = data?.system.dataUpdateInterval ?? 30
  const minimum = Number.isFinite(seconds) ? Math.max(5, Math.min(seconds, 86400)) * 1000 : 30000
  return (providerInterval: number) => providerInterval === 0 ? 0 : Math.max(minimum, providerInterval)
}
