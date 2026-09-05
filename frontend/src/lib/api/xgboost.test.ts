import { afterEach, describe, expect, it, vi } from 'vitest'

import { fetchXGBoost } from './xgboost'

describe('XGBoost API client', () => {
  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('allows a cold model response to take up to 45 seconds', async () => {
    vi.useFakeTimers()
    const payload = { stocks: [], feature_importance: {} }
    const backendFetch = vi.fn((_url: string, init?: RequestInit) =>
      new Promise<Response>((resolve, reject) => {
        const responseTimer = setTimeout(() => {
          resolve(Response.json(payload))
        }, 44_000)
        init?.signal?.addEventListener('abort', () => {
          clearTimeout(responseTimer)
          reject(new DOMException('aborted', 'AbortError'))
        })
      })
    )
    vi.stubGlobal('fetch', backendFetch)

    const request = fetchXGBoost('/strategy/ai-xgboost?top_n=20')
    let settled = false
    void request.finally(() => {
      settled = true
    })

    await vi.advanceTimersByTimeAsync(20_500)
    expect(settled).toBe(false)

    await vi.advanceTimersByTimeAsync(23_500)
    await expect(request).resolves.toEqual(payload)
    expect(backendFetch).toHaveBeenCalledTimes(1)
  })

  it('stops after the 45-second frontend budget without an automatic retry', async () => {
    vi.useFakeTimers()
    const backendFetch = vi.fn((_url: string, init?: RequestInit) =>
      new Promise<Response>((_resolve, reject) => {
        init?.signal?.addEventListener('abort', () => {
          reject(new DOMException('aborted', 'AbortError'))
        })
      })
    )
    vi.stubGlobal('fetch', backendFetch)

    let settled = false
    void fetchXGBoost('/strategy/ai-xgboost?top_n=20').catch(() => {
      settled = true
    })

    await vi.advanceTimersByTimeAsync(45_000)

    expect(settled).toBe(true)
    expect(backendFetch).toHaveBeenCalledTimes(1)
  })
})
