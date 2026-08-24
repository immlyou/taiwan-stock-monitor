import { describe, expect, it } from 'vitest'

import { getBatchQuoteRefreshInterval, getQuoteRefreshInterval, quoteStatusLabel } from './realtime'

describe('Taiwan market quote refresh policy', () => {
  it('polls every 15 seconds while the market is trading', () => {
    expect(getQuoteRefreshInterval(new Date('2026-08-24T02:00:00Z'))).toBe(15_000)
  })

  it('uses a slower heartbeat before open and after close', () => {
    expect(getQuoteRefreshInterval(new Date('2026-08-24T00:00:00Z'))).toBe(60_000)
    expect(getQuoteRefreshInterval(new Date('2026-08-24T07:00:00Z'))).toBe(300_000)
  })

  it('slows large batches enough to stay inside the default Fugle minute budget', () => {
    const trading = new Date('2026-08-24T02:00:00Z')
    expect(getBatchQuoteRefreshInterval(10, trading)).toBe(15_000)
    expect(getBatchQuoteRefreshInterval(50, trading)).toBe(60_000)
  })
})

describe('quote source status', () => {
  it('makes live and fallback states explicit', () => {
    expect(quoteStatusLabel({ source: 'fugle', is_realtime: true, freshness: 'realtime' }))
      .toBe('即時 · Fugle')
    expect(quoteStatusLabel({ source: 'twse', is_realtime: false, freshness: 'close' }))
      .toBe('休市 · TWSE')
    expect(quoteStatusLabel({ source: 'finlab', is_realtime: false, freshness: 'close' }))
      .toBe('收盤 · FinLab')
    expect(quoteStatusLabel({ source: 'unavailable', freshness: 'unavailable' }))
      .toBe('報價不可用')
  })
})
