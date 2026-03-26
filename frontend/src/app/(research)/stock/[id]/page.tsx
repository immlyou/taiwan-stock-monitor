interface StockDetailPageProps {
  params: Promise<{ id: string }>
}

export default async function StockDetailPage({ params }: StockDetailPageProps) {
  const { id } = await params

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold" style={{ color: 'var(--foreground)' }}>
          📊 個股分析 — {id}
        </h1>
      </div>
      <div
        className="rounded-lg p-12 text-center"
        style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
      >
        <p className="text-4xl mb-4">🚧</p>
        <p className="text-lg font-semibold" style={{ color: 'var(--foreground)' }}>
          建置中
        </p>
        <p className="text-sm mt-2" style={{ color: 'var(--muted-foreground)' }}>
          個股 {id} 詳細分析功能即將推出
        </p>
      </div>
    </div>
  )
}
