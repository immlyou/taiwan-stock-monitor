'use client'

import Link from 'next/link'
import { NAVIGATION_GROUPS } from '@/lib/navigation/catalog'

export default function OverviewPage() {
  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold flex items-center gap-2" style={{ color: 'var(--foreground)' }}>✨ 功能總覽</h1>
        <p className="text-sm mt-1" style={{ color: 'var(--muted-foreground)' }}>
          所有功能一覽，點卡片直接前往。標記 <span style={{ color: 'var(--primary)' }}>NEW</span> 為近期新增。
        </p>
      </div>

      <div className="space-y-7">
        {NAVIGATION_GROUPS.map((g) => {
          const GroupIcon = g.icon
          return (
          <section key={g.label}>
            <h2 className="text-sm font-semibold mb-3 flex items-center gap-1.5" style={{ color: 'var(--foreground)' }}>
              <GroupIcon className="h-4 w-4" />{g.label}
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {g.items.map((f) => (
                <Link key={f.href} href={f.href}
                  className="rounded-lg p-4 transition-colors hover:bg-white/5 block"
                  style={{ background: 'var(--card)', border: '1px solid var(--border)' }}>
                  <div className="flex items-center gap-2 mb-1">
                    <f.icon className="h-5 w-5" style={{ color: 'var(--primary)' }} />
                    <span className="font-semibold text-sm" style={{ color: 'var(--foreground)' }}>{f.label}</span>
                    {f.isNew && (
                      <span className="text-[10px] font-bold px-1.5 py-0.5 rounded"
                        style={{ background: 'var(--stock-up-weak)', color: 'var(--stock-up)' }}>NEW</span>
                    )}
                  </div>
                  <p className="text-xs leading-relaxed" style={{ color: 'var(--muted-foreground)' }}>{f.description}</p>
                </Link>
              ))}
            </div>
          </section>
          )
        })}
      </div>
    </div>
  )
}
