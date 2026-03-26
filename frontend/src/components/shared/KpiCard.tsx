import { cn } from '@/lib/utils'
import { Skeleton } from '@/components/ui/skeleton'

interface KpiCardProps {
  title: string
  value: string
  subValue?: string
  change?: number
  changeLabel?: string
  accentColor?: string
  isLoading?: boolean
  className?: string
}

export function KpiCard({
  title,
  value,
  subValue,
  change,
  changeLabel,
  accentColor = 'var(--primary)',
  isLoading = false,
  className,
}: KpiCardProps) {
  const changeColor =
    change !== undefined
      ? change > 0
        ? 'var(--stock-up)'
        : change < 0
          ? 'var(--stock-down)'
          : 'var(--stock-flat)'
      : undefined

  if (isLoading) {
    return (
      <div
        className={cn('rounded-lg p-4 relative overflow-hidden', className)}
        style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
      >
        <div className="absolute top-0 left-0 right-0 h-1 rounded-t-lg" style={{ background: accentColor }} />
        <Skeleton className="h-3 w-20 mb-3" style={{ background: 'var(--secondary)' }} />
        <Skeleton className="h-7 w-28 mb-2" style={{ background: 'var(--secondary)' }} />
        <Skeleton className="h-3 w-16" style={{ background: 'var(--secondary)' }} />
      </div>
    )
  }

  return (
    <div
      className={cn('rounded-lg p-4 relative overflow-hidden', className)}
      style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
    >
      {/* 頂部 accent bar */}
      <div
        className="absolute top-0 left-0 right-0 h-1 rounded-t-lg"
        style={{ background: accentColor }}
      />

      {/* 標題 */}
      <p className="text-xs font-medium mb-2 mt-1" style={{ color: 'var(--muted-foreground)' }}>
        {title}
      </p>

      {/* 主要數值 */}
      <p className="text-2xl font-bold tabular-nums" style={{ color: 'var(--foreground)' }}>
        {value}
      </p>

      {/* 次要數值 */}
      {subValue && (
        <p className="text-sm mt-0.5 tabular-nums" style={{ color: 'var(--muted-foreground)' }}>
          {subValue}
        </p>
      )}

      {/* 漲跌數值 */}
      {change !== undefined && (
        <div className="flex items-center gap-1 mt-1">
          <span className="text-sm font-semibold tabular-nums" style={{ color: changeColor }}>
            {change > 0 ? '+' : ''}{change.toFixed(2)}
          </span>
          {changeLabel && (
            <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
              {changeLabel}
            </span>
          )}
        </div>
      )}
    </div>
  )
}
