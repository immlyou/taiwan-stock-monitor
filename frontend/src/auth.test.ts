import { beforeEach, describe, expect, it, vi } from 'vitest'
import NextAuth, { type NextAuthConfig } from 'next-auth'

const { accountRequest } = vi.hoisted(() => ({ accountRequest: vi.fn() }))
vi.mock('next-auth', () => ({ default: vi.fn(() => ({})) }))
vi.mock('@/lib/auth/account-server', () => ({
  accountRequest,
  AccountAccessError: class extends Error { constructor(public status: number) { super() } },
}))
import './auth'
import { AccountAccessError } from '@/lib/auth/account-server'

const config = vi.mocked(NextAuth).mock.calls[0][0] as NextAuthConfig
const signIn = config.callbacks!.signIn!
function identity(verified: boolean) {
  return {
    user: { id: '123', email: 'member@example.test', name: 'Member' },
    account: { provider: 'google', providerAccountId: '123', type: 'oidc' as const },
    profile: { email: 'member@example.test', email_verified: verified },
  }
}

describe('Google login account registry', () => {
  beforeEach(() => { accountRequest.mockReset() })
  it('never registers an unverified Google email', async () => {
    expect(await signIn(identity(false))).toBe(false)
    expect(accountRequest).not.toHaveBeenCalled()
  })
  it('requires provider email to match the verified identity', async () => {
    const input = identity(true)
    input.profile.email = 'other@example.test'
    expect(await signIn(input)).toBe(false)
    expect(accountRequest).not.toHaveBeenCalled()
  })
  it('allows an invited account only after backend acceptance', async () => {
    accountRequest.mockResolvedValue({ role: 'member' })
    expect(await signIn(identity(true))).toBe(true)
    const [path, init] = accountRequest.mock.calls[0]
    expect(path).toBe('/internal/accounts/google-login')
    expect(JSON.parse(init.body)).toMatchObject({ user_id: 'google_123', email: 'member@example.test' })
  })
  it('rejects disabled or uninvited accounts', async () => {
    accountRequest.mockRejectedValue(new AccountAccessError(403))
    expect(await signIn(identity(true))).toBe(false)
  })
  it('fails closed with a retryable message when account storage is unavailable', async () => {
    accountRequest.mockRejectedValue(new AccountAccessError(503))
    expect(await signIn(identity(true))).toBe('/login?error=ServiceUnavailable')
  })
})
