'use client'

import { cn } from '@/lib/utils'

interface SwitchProps {
  checked: boolean
  onCheckedChange: (checked: boolean) => void
  disabled?: boolean
  id?: string
  'aria-label'?: string
  'aria-labelledby'?: string
  className?: string
}

/**
 * 無障礙開關（dependency-free）。
 * 原生 button + role="switch" + aria-checked，支援鍵盤（Space/Enter）與 focus ring，
 * 取代各頁手刻的 div toggle（缺 ARIA / 鍵盤導航）。
 */
export function Switch({
  checked,
  onCheckedChange,
  disabled = false,
  id,
  className,
  ...aria
}: SwitchProps) {
  return (
    <button
      type="button"
      role="switch"
      id={id}
      aria-checked={checked}
      aria-label={aria['aria-label']}
      aria-labelledby={aria['aria-labelledby']}
      disabled={disabled}
      onClick={() => !disabled && onCheckedChange(!checked)}
      className={cn(
        'relative inline-flex h-5 w-10 shrink-0 items-center rounded-full transition-colors',
        'outline-none focus-visible:ring-2 focus-visible:ring-offset-2',
        'disabled:cursor-not-allowed disabled:opacity-50',
        className
      )}
      style={{
        background: checked ? 'var(--primary)' : 'var(--secondary)',
        // @ts-expect-error CSS custom property for focus ring color
        '--tw-ring-color': 'var(--ring)',
        '--tw-ring-offset-color': 'var(--card)',
      }}
    >
      <span
        className="pointer-events-none absolute top-0.5 h-4 w-4 rounded-full bg-white transition-all"
        style={{ left: checked ? '1.375rem' : '0.125rem' }}
      />
    </button>
  )
}
