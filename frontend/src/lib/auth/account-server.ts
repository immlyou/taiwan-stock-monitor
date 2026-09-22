import 'server-only'
import type { Account } from './accounts'
import type { ProxyIdentity } from './identity'

export class AccountAccessError extends Error {
  constructor(public status: number) { super('account_access_failed') }
}

export async function accountRequest(path: string, init: RequestInit): Promise<Account> {
  if (!process.env.STOCK_API_KEY) throw new AccountAccessError(503)
  try {
    const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}${path}`, {
      ...init,
      headers: {
        'content-type': 'application/json',
        authorization: `Bearer ${process.env.STOCK_API_KEY}`,
        ...init.headers,
      },
      cache: 'no-store', signal: AbortSignal.timeout(8000),
    })
    if (!response.ok) throw new AccountAccessError(response.status)
    return await response.json() as Account
  } catch (error) {
    if (error instanceof AccountAccessError) throw error
    throw new AccountAccessError(503)
  }
}

export function getCurrentAccount(identity: Extract<ProxyIdentity, { authenticated: true }>) {
  return accountRequest('/accounts/me', { headers: {
    'x-user-id': identity.userId,
    'x-user-email': identity.email,
    'x-bootstrap-email': process.env.AUTH_ALLOWED_EMAIL || '',
  } })
}
