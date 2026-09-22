'use client'
import useSWR from 'swr'
import { useSession } from 'next-auth/react'
import { fetchAPI } from '@/lib/api/client'
import type { Account } from '@/lib/auth/accounts'

export function useAccount() {
  const { status } = useSession()
  return useSWR<Account>(status === 'authenticated' ? '/accounts/me' : null,
    (path: string) => fetchAPI<Account>(path), {
      refreshInterval: 30000, revalidateOnFocus: true, shouldRetryOnError: false,
    })
}
