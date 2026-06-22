import { cn } from '@/lib/utils'

/**
 * 低調的「更新失敗，顯示前次資料」提示。
 *
 * 用於 stale-while-revalidate：背景 revalidate 失敗（逾時 / 後端暫態）時，
 * 頁面繼續顯示上次成功取得的資料，並以這條 banner 告知使用者資料非最新，
 * 而不是把整頁變成錯誤畫面。
 */
export function StaleBanner({ className }: { className?: string }) {
  return (
    <div
      role="status"
      aria-live="polite"
      className={cn(
        'flex items-center gap-2 rounded-md px-3 py-2 mb-4 text-xs',
        className
      )}
      style={{
        background: 'var(--muted)',
        color: 'var(--muted-foreground)',
        border: '1px solid var(--border)',
      }}
    >
      <span aria-hidden="true">⚠️</span>
      <span>更新失敗，顯示前次資料（背景持續重試中）</span>
    </div>
  )
}
