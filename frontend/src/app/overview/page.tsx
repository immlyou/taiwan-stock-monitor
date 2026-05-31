'use client'

import Link from 'next/link'

interface Feature {
  href: string
  icon: string
  title: string
  desc: string
  isNew?: boolean
}
interface Group { label: string; icon: string; items: Feature[] }

const GROUPS: Group[] = [
  {
    label: 'AI 新功能', icon: '✨',
    items: [
      { href: '/advisor', icon: '🧭', title: 'AI 投資顧問', desc: '持股健檢→配置建議→達標可行性→Claude 操盤觀點，可一鍵套用；支援截圖匯入持股', isNew: true },
      { href: '/ai-pick', icon: '🤖', title: 'AI 智慧選股', desc: 'XGBoost 多因子預測排序選股', isNew: true },
      { href: '/trading-radar', icon: '📡', title: 'AI 操盤雷達', desc: '個股多維度操盤訊號' },
      { href: '/ai-anomaly', icon: '⚠️', title: 'AI 異常警報', desc: '依嚴重度分組的異常偵測' },
    ],
  },
  {
    label: '市場動態', icon: '📊',
    items: [
      { href: '/dashboard', icon: '💼', title: '持倉總覽', desc: 'KPI + 持股明細（走勢 Sparkline、排序/匯出）', isNew: true },
      { href: '/realtime', icon: '💹', title: '即時報價', desc: '指數、個股、自選股報價（含成交量/額）' },
      { href: '/morning-report', icon: '🌅', title: '每日晨報', desc: '市場總覽 + 新聞情緒標籤 + AI 分析' },
      { href: '/heatmap', icon: '🗺️', title: '市場熱力圖', desc: '依市值/漲跌的產業熱力圖' },
      { href: '/money-flow', icon: '💸', title: '資金流向', desc: '三大法人買賣超' },
      { href: '/after-hours', icon: '📋', title: '盤後總覽', desc: '收盤統計 + 三策略 AI 選股（🥇🥈🥉）' },
    ],
  },
  {
    label: '研究分析', icon: '🔬',
    items: [
      { href: '/stock/2330', icon: '📈', title: '個股分析', desc: '量化評分卡 + AI 摘要 + 技術/籌碼/財報；可截圖辨識跳轉', isNew: true },
      { href: '/technical', icon: '📉', title: '技術分析', desc: '指標圖表' },
      { href: '/compare', icon: '⚖️', title: '比較分析', desc: '多股比較（走勢 Sparkline）' },
      { href: '/chip', icon: '💰', title: '籌碼分析', desc: '三大法人/籌碼明細表（可排序匯出）' },
      { href: '/financials', icon: '📑', title: '財報分析', desc: '月營收/PE/PB/殖利率' },
      { href: '/industry', icon: '🏭', title: '產業分析', desc: '產業輪動與比較' },
      { href: '/risk', icon: '⚠️', title: '風險分析', desc: 'VaR/波動/回撤等風險指標' },
    ],
  },
  {
    label: '選股策略', icon: '🎯',
    items: [
      { href: '/screener', icon: '🔍', title: '選股篩選', desc: '量化排行 + 條件篩選（排序/匯出）' },
      { href: '/backtest', icon: '📊', title: '回測分析', desc: '策略歷史績效' },
      { href: '/optimizer', icon: '🎯', title: '參數優化', desc: 'Grid Search 參數尋優' },
      { href: '/predictions', icon: '🔮', title: '預測驗證', desc: '預測追蹤（可排序匯出）' },
      { href: '/hidden-gems', icon: '💎', title: '遺珠掃描', desc: '低估值/營收爆發掃描' },
    ],
  },
  {
    label: '投資管理', icon: '💼',
    items: [
      { href: '/portfolio', icon: '💼', title: '投資組合', desc: '持股損益追蹤；📷 截圖匯入持股', isNew: true },
      { href: '/watchlist', icon: '⭐', title: '自選股', desc: '追蹤清單；📷 截圖匯入代號', isNew: true },
      { href: '/journal', icon: '📝', title: '交易日誌', desc: '交易紀錄 + AI 回顧（Markdown 報告）' },
      { href: '/alerts', icon: '🔔', title: '警報設定', desc: '價格/技術警報' },
    ],
  },
]

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
        {GROUPS.map((g) => (
          <section key={g.label}>
            <h2 className="text-sm font-semibold mb-3 flex items-center gap-1.5" style={{ color: 'var(--foreground)' }}>
              <span>{g.icon}</span>{g.label}
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {g.items.map((f) => (
                <Link key={f.href} href={f.href}
                  className="rounded-lg p-4 transition-colors hover:bg-white/5 block"
                  style={{ background: 'var(--card)', border: '1px solid var(--border)' }}>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-lg">{f.icon}</span>
                    <span className="font-semibold text-sm" style={{ color: 'var(--foreground)' }}>{f.title}</span>
                    {f.isNew && (
                      <span className="text-[10px] font-bold px-1.5 py-0.5 rounded"
                        style={{ background: 'var(--stock-up-weak)', color: 'var(--stock-up)' }}>NEW</span>
                    )}
                  </div>
                  <p className="text-xs leading-relaxed" style={{ color: 'var(--muted-foreground)' }}>{f.desc}</p>
                </Link>
              ))}
            </div>
          </section>
        ))}
      </div>
    </div>
  )
}
