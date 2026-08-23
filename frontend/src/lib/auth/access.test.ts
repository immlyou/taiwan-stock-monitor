import { describe, expect, it } from 'vitest'

import { canAccessPath, isAllowedGoogleAccount } from './access'

describe('Google account allowlist', () => {
  it('allows the configured owner account', () => {
    expect(
      isAllowedGoogleAccount(
        'imchris.yu@gmail.com',
        'imchris.yu@gmail.com'
      )
    ).toBe(true)
  })

  it('normalizes whitespace and letter case', () => {
    expect(
      isAllowedGoogleAccount(
        'ImChris.Yu@Gmail.com',
        '  imchris.yu@gmail.com  '
      )
    ).toBe(true)
  })

  it.each([
    ['another@gmail.com', 'imchris.yu@gmail.com'],
    [null, 'imchris.yu@gmail.com'],
    ['imchris.yu@gmail.com', undefined],
  ])('rejects an unlisted or unconfigured account', (email, configuredEmail) => {
    expect(isAllowedGoogleAccount(email, configuredEmail)).toBe(false)
  })
})

describe('page authorization policy', () => {
  it.each(['/login', '/api/auth/signin', '/api/auth/callback/google', '/api/settings']) (
    'keeps auth and session-enforcing API handlers reachable: %s',
    (path) => {
      expect(canAccessPath(path, false)).toBe(true)
    }
  )

  it('requires a session for application pages', () => {
    expect(canAccessPath('/dashboard', false)).toBe(false)
    expect(canAccessPath('/dashboard', true)).toBe(true)
  })
})
