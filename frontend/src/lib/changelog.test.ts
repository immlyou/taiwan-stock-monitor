import { describe, expect, it } from 'vitest'

import {
  API_VERSION,
  CURRENT_VERSION,
  FRONTEND_VERSION,
  RECENT_CHANGELOG,
  RELEASE_MANIFEST,
} from './changelog'

describe('release history', () => {
  it('uses the newest release as the current system version', () => {
    expect(CURRENT_VERSION).toBe('v5.2.0')
    expect(FRONTEND_VERSION).toBe('5.2.0')
    expect(API_VERSION).toBe('5.2.0')
    expect(RELEASE_MANIFEST.releaseDate).toBe('2026-08-28')
    expect(RECENT_CHANGELOG[0].version).toBe(CURRENT_VERSION)
  })

  it('keeps every post-v4 release ordered, unique, and documented', () => {
    expect(RECENT_CHANGELOG.map((release) => release.version)).toEqual([
      'v5.2.0',
      'v5.1.1',
      'v5.1.0',
      'v5.0.1',
      'v5.0.0',
      'v4.1.0',
      'v4.0.1',
    ])
    expect(new Set(RECENT_CHANGELOG.map((release) => release.version)).size).toBe(
      RECENT_CHANGELOG.length
    )
    expect(RECENT_CHANGELOG.every((release) => release.changes.length > 0)).toBe(true)
  })

  it('covers the major authentication, realtime quote, and XGBoost changes', () => {
    const log = RECENT_CHANGELOG.flatMap((release) => release.changes).join('\n')

    expect(log).toMatch(/Google OAuth/)
    expect(log).toMatch(/資料隔離/)
    expect(log).toMatch(/blocking pipeline/)
    expect(log).toMatch(/Fugle \/ TWSE/)
    expect(log).toMatch(/FinLab.*fallback/)
    expect(log).toMatch(/45 秒/)
    expect(log).toMatch(/65 秒/)
    expect(log).toMatch(/single-flight/)
  })
})
