'use client'

import useSWR from 'swr'
import { fetchAPI, QuotaExceededError } from '@/lib/api/client'

interface HealthResponse {
  status?: string
  error?: string
}

export function useQuotaStatus() {
  const { data, error } = useSWR<HealthResponse>(
    '/health',
    (path: string) => fetchAPI<HealthResponse>(path),
    {
      refreshInterval: 30000,
      shouldRetryOnError: false,
    }
  )

  const isExceeded =
    error instanceof QuotaExceededError ||
    data?.status === 'degraded' ||
    (typeof data?.error === 'string' && data.error.includes('Usage exceed'))

  return { isExceeded }
}
