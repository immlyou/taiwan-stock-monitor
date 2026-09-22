import { describe, expect, it } from 'vitest'

import { canAccessPath } from './access'

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
