import { describe, expect, it } from 'vitest'
import {
  DEFAULT_DASHBOARD_WIDGET_TYPES,
  isSupportedDashboardWidgetType,
} from './widgets'

describe('dashboard widget contract', () => {
  it('has a renderer for every default widget', () => {
    expect(DEFAULT_DASHBOARD_WIDGET_TYPES.every(isSupportedDashboardWidgetType)).toBe(true)
    expect(DEFAULT_DASHBOARD_WIDGET_TYPES).toContain('market_summary')
    expect(DEFAULT_DASHBOARD_WIDGET_TYPES).toContain('portfolio_kpi')
  })

  it('rejects unknown widget types instead of exposing an internal identifier', () => {
    expect(isSupportedDashboardWidgetType('internal_widget')).toBe(false)
  })
})
