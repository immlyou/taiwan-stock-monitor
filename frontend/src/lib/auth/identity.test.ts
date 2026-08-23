import { describe, expect, it } from 'vitest'

import { identityFromSession } from './identity'

describe('authenticated proxy identity', () => {
  it('rejects a request without an authenticated Google session', () => {
    expect(identityFromSession(null)).toEqual({ authenticated: false })
  })

  it('returns the stable Google user id for an authenticated session', () => {
    expect(
      identityFromSession({
        user: {
          id: 'google_109876543210',
          email: 'investor@example.com',
        },
      })
    ).toEqual({
      authenticated: true,
      userId: 'google_109876543210',
      email: 'investor@example.com',
    })
  })

  it('rejects an unsafe user id instead of forwarding it to the backend', () => {
    expect(
      identityFromSession({
        user: { id: '../other-user', email: 'investor@example.com' },
      })
    ).toEqual({ authenticated: false })
  })
})
