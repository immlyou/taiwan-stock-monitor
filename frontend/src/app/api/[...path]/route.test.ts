import { beforeEach, describe, expect, it, vi } from 'vitest'
import { NextRequest } from 'next/server'

const { authMock } = vi.hoisted(() => ({ authMock: vi.fn() }))

vi.mock('@/auth', () => ({
  auth: authMock,
}))

import { GET } from './route'

const context = { params: Promise.resolve({ path: ['settings'] }) }

describe('authenticated backend proxy', () => {
  beforeEach(() => {
    authMock.mockReset()
    vi.unstubAllGlobals()
    vi.unstubAllEnvs()
    vi.stubEnv('AUTH_ALLOWED_EMAIL', 'imchris.yu@gmail.com')
  })

  it('returns 401 without calling the backend when there is no session', async () => {
    authMock.mockResolvedValue(null)
    const backendFetch = vi.fn()
    vi.stubGlobal('fetch', backendFetch)

    const response = await GET(
      new NextRequest('https://stocks.example/api/settings'),
      context
    )

    expect(response.status).toBe(401)
    expect(await response.json()).toEqual({ error: 'authentication_required' })
    expect(backendFetch).not.toHaveBeenCalled()
  })

  it('forwards only the server-verified user id for an authenticated session', async () => {
    authMock.mockResolvedValue({
      user: { id: 'google_109876543210', email: 'imchris.yu@gmail.com' },
    })
    const backendFetch = vi.fn().mockResolvedValue(
      Response.json({ ok: true }, { status: 200 })
    )
    vi.stubGlobal('fetch', backendFetch)

    const response = await GET(
      new NextRequest('https://stocks.example/api/settings', {
        headers: { 'x-user-id': 'attacker' },
      }),
      context
    )

    expect(response.status).toBe(200)
    const [, init] = backendFetch.mock.calls[0] as [string, RequestInit]
    const headers = new Headers(init.headers)
    expect(headers.get('x-user-id')).toBe('google_109876543210')
    expect(headers.get('x-user-id')).not.toBe('attacker')
  })
})
