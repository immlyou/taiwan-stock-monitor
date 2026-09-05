import { describe, expect, it } from 'vitest'
import {
  NAVIGATION_GROUPS,
  isNavigationItemActive,
} from './catalog'

describe('navigation catalog', () => {
  const items = NAVIGATION_GROUPS.flatMap((group) => group.items)

  it('contains every primary destination exactly once', () => {
    const hrefs = items.map((item) => item.href)
    expect(hrefs).toContain('/')
    expect(hrefs).toContain('/strategies')
    expect(new Set(hrefs).size).toBe(hrefs.length)
  })

  it('classifies holdings with investment management', () => {
    const investment = NAVIGATION_GROUPS.find((group) => group.label === '投資管理')
    expect(investment?.items.map((item) => item.href)).toContain('/dashboard')
  })

  it('matches dynamic stock routes without making root match every page', () => {
    const stock = items.find((item) => item.href === '/stock/2330')!
    const home = items.find((item) => item.href === '/')!
    expect(isNavigationItemActive(stock, '/stock/4933')).toBe(true)
    expect(isNavigationItemActive(home, '/portfolio')).toBe(false)
  })
})
