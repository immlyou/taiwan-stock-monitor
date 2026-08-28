export const DEFAULT_DASHBOARD_WIDGET_TYPES = [
  'market_summary',
  'portfolio_kpi',
  'smart_alerts',
  'industry_rotation',
  'score_upgrades',
] as const

export type DashboardWidgetType = (typeof DEFAULT_DASHBOARD_WIDGET_TYPES)[number]

const SUPPORTED_WIDGET_TYPES = new Set<string>(DEFAULT_DASHBOARD_WIDGET_TYPES)

export function isSupportedDashboardWidgetType(
  type: string
): type is DashboardWidgetType {
  return SUPPORTED_WIDGET_TYPES.has(type)
}
