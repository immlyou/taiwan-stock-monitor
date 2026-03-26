import { MarketDashboard } from '@/components/dashboard/MarketDashboard'

export default function HomePage() {
  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold" style={{ color: 'var(--foreground)' }}>
          市場戰情中心
        </h1>
        <p className="text-sm mt-1" style={{ color: 'var(--muted-foreground)' }}>
          台灣股票市場即時總覽
        </p>
      </div>
      <MarketDashboard />
    </div>
  )
}
