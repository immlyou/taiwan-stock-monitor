import { afterEach, describe, expect, it, vi } from 'vitest'

import { ApiError, fetchAPI } from './client'

describe('API retry policy', () => {
  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('makes at most one retry for a transient GET failure', async () => {
    vi.useFakeTimers()
    const backendFetch = vi
      .fn()
      .mockImplementation(async () =>
        new Response('temporarily unavailable', { status: 503 })
      )
    vi.stubGlobal('fetch', backendFetch)

    const request = fetchAPI('/market/summary').catch((error) => error)
    await vi.runAllTimersAsync()

    await expect(request).resolves.toBeInstanceOf(ApiError)
    expect(backendFetch).toHaveBeenCalledTimes(2)
  })
})
