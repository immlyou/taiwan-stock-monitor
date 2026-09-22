'use client'

import useSWR from 'swr'
import { fetchAPI } from '@/lib/api/client'
import { KpiCard } from '@/components/shared/KpiCard'

interface Position {
  stock_id: string
  status: string
  entry_date: string | null
  exit_date: string | null
  net_return: number | null
  share_multiplier: number
  mark_date?: string
  events: string[]
}
interface Study {
  status: string
  data_as_of: string
  summary: { periods_requested: number; accounted_periods: number; settled_periods: number; open_periods: number; unresolved_periods: number }
  original_summary: { complete_top_n_periods: number; mean_ic: number | null }
  events: { id: string; source_url: string }[]
  periods: { date: string; status: string; net_return: number | null; positions: Position[] }[]
}

const labels: Record<string, string> = {
  closed_on_schedule: '準時出場', closed_delayed: '延後出場', unfilled_cash: '未成交留現金',
  open_suspended: '停牌未平倉', settled_cash: '現金結算', unresolved_data: '資料待核對',
  settled: '已結清', open_position: '仍有未平倉',
}
const percent = (value: number | null) => value == null ? '—' : `${(value * 100).toFixed(2)}%`

export function XGBoostLifecyclePanel() {
  const { data, error, isLoading, isValidating, mutate } = useSWR<Study>('/strategy/ai-xgboost/lifecycle', fetchAPI)
  return (
    <section className="rounded-lg border p-4 space-y-4 mt-6" aria-label="XGBoost 交易生命週期研究"
      style={{ background: 'var(--card)', borderColor: 'var(--border)' }}>
      <h2 className="text-lg font-semibold">XGBoost 交易生命週期研究</h2>
      {isLoading && <p role="status">研究報告載入中…</p>}
      {error && <div role="alert">
        <p>研究報告載入失敗{data ? '，保留上次結果。' : '。'}</p>
        <button className="underline" disabled={isValidating} onClick={() => void mutate()}>重試研究報告</button>
      </div>}
      {data && data.status !== 'ok' && <p>尚未產生交易生命週期研究報告。</p>}
      {data?.status === 'ok' && <>
        <p className="text-sm" style={{ color: 'var(--muted-foreground)' }}>
          固定歷史快照，截至 {data.data_as_of}，不是即時模型績效。保留原始 Top 20，不換股、不把缺價補成零報酬。
        </p>
        <div className="grid gap-3 sm:grid-cols-3">
          <KpiCard title="期數已核對（含未平倉）" value={`${data.summary.accounted_periods} / ${data.summary.periods_requested}`} />
          <KpiCard title="期數已結清" value={`${data.summary.settled_periods} / ${data.summary.periods_requested}`} subValue={`未平倉 ${data.summary.open_periods} 期；待核對 ${data.summary.unresolved_periods} 期`} />
          <KpiCard title="原始指定日報價完整期數" value={`${data.original_summary.complete_top_n_periods} / ${data.summary.periods_requested}`} subValue={`原始平均 IC：${data.original_summary.mean_ic ?? '—'}（未重算）`} />
        </div>
        <p role="note" className="text-sm">
          核對完成不等於交易已結清或模型有效。未買到保留現金；到期無價延後出場；拆股依已核對公告調整股數。
          停牌持倉不算已實現損益。各期獨立等權試算，延後出場會改變持有期，不能串成年化績效。
          費用沿用原研究情境；日收盤有價不保證實際可成交。事件清單非完整公司行動／股息資料，因此不是含息總報酬。
        </p>
        <div className="space-y-2">
          {data.periods.map(period => <details key={period.date} className="rounded border p-3" style={{ borderColor: 'var(--border)' }}>
            <summary className="cursor-pointer text-sm">
              {period.date} · {labels[period.status] ?? period.status} · 結清期報酬 {percent(period.net_return)}
            </summary>
            <div className="overflow-x-auto mt-3">
              <table className="w-full text-sm text-left">
                <thead><tr>{['代號', '狀態', '進場日', '實際出場日', '淨報酬／現金', '事件依據'].map(h => <th key={h} className="p-2">{h}</th>)}</tr></thead>
                <tbody>{period.positions.map(row => <tr key={row.stock_id}>
                  <td className="p-2">{row.stock_id}</td>
                  <td className="p-2">{labels[row.status] ?? row.status}{row.share_multiplier !== 1 ? `（股數 ×${row.share_multiplier}）` : ''}
                    {row.mark_date && <span className="block text-xs">舊估值日 {row.mark_date}，非成交</span>}</td>
                  <td className="p-2">{row.entry_date ?? '未成交'}</td>
                  <td className="p-2">{row.exit_date ?? '—'}</td>
                  <td className="p-2">{row.status === 'unfilled_cash' ? '現金保留（非股票報酬）' : percent(row.net_return)}</td>
                  <td className="p-2">{row.events.map(id => {
                    const event = data.events.find(e => e.id === id)
                    return event ? <a key={id} className="block underline" href={event.source_url} target="_blank" rel="noopener noreferrer">官方公告</a> : null
                  })}</td>
                </tr>)}</tbody>
              </table>
            </div>
          </details>)}
        </div>
        <a className="inline-block underline text-sm" href="/api/strategy/ai-xgboost/lifecycle" download="xgboost-lifecycle.json">下載逐筆研究 JSON（含假設與來源雜湊）</a>
      </>}
    </section>
  )
}
