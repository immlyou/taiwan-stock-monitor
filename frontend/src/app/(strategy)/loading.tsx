export default function Loading() {
  return (
    <div className="animate-pulse space-y-6">
      {/* 標題骨架 */}
      <div className="space-y-2">
        <div className="h-8 w-48 rounded-md bg-gray-200 dark:bg-gray-700" />
        <div className="h-4 w-64 rounded-md bg-gray-200 dark:bg-gray-700" />
      </div>

      {/* KPI 卡片骨架 */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="rounded-lg border p-4 space-y-2" style={{ borderColor: 'var(--border)' }}>
            <div className="h-4 w-20 rounded bg-gray-200 dark:bg-gray-700" />
            <div className="h-6 w-16 rounded bg-gray-200 dark:bg-gray-700" />
          </div>
        ))}
      </div>

      {/* 主內容骨架 */}
      <div className="rounded-lg border p-4 space-y-3" style={{ borderColor: 'var(--border)' }}>
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="h-4 rounded bg-gray-200 dark:bg-gray-700" style={{ width: `${85 - i * 5}%` }} />
        ))}
      </div>
    </div>
  )
}
