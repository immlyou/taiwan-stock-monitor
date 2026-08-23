'use client'

import { useState, useEffect, useMemo } from 'react'
import useSWR, { useSWRConfig } from 'swr'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { fetchAPI } from '@/lib/api/client'
import { KpiCard } from '@/components/shared/KpiCard'
import { EmptyState } from '@/components/shared/EmptyState'
import { StockInput } from '@/components/shared/StockInput'
import { formatCurrency, formatPercent, getChangeColorVar } from '@/lib/utils/format'
import { ratingColor } from '@/lib/constants/chartColors'

interface PortfolioListItem { id: string; name: string; holdings_count: number }
interface PortfoliosListResponse { total: number; portfolios: PortfolioListItem[] }

interface HealthHolding { stock_id: string; name: string; shares: number; price: number; value: number; score: number | null; rating: string; weight: number }
interface PlanBuy { stock_id: string; name: string; shares: number; amount: number; score: number; rating: string; reason: string }
interface PlanSell { stock_id: string; name: string; shares: number; amount: number; reason: string }
interface AdvisorResult {
  health: { holdings: HealthHolding[]; avg_score: number; total_value: number; top_weight: number; concentration: string }
  plan: { buys: PlanBuy[]; sells: PlanSell[]; freed_cash: number; deployed: number; cash_after: number }
  feasibility: { target_roi: number; estimated_annual_return: number; verdict: string; note: string } | null
  proposed_holdings: { stock_id: string; shares: number; cost_price: number }[]
  narrative: string
  narrative_error: string | null
}

const RISK_OPTIONS = [
  { value: 'conservative', label: '保守' },
  { value: 'moderate', label: '穩健' },
  { value: 'aggressive', label: '積極' },
]

const card = { background: 'var(--card)', border: '1px solid var(--border)' }
const inputStyle = { background: 'var(--secondary)', color: 'var(--foreground)', border: '1px solid var(--border)' }

function verdictColor(v: string) {
  if (v === '可行') return 'var(--stock-down)'
  if (v === '具挑戰') return 'var(--flow-trust)'
  return 'var(--stock-up)'
}

const MD = {
  h1: (p: React.ComponentProps<'h1'>) => <h2 className="text-base font-bold mt-3 mb-1" style={{ color: 'var(--foreground)' }} {...p} />,
  h2: (p: React.ComponentProps<'h2'>) => <h2 className="text-base font-bold mt-3 mb-1" style={{ color: 'var(--foreground)' }} {...p} />,
  h3: (p: React.ComponentProps<'h3'>) => <h3 className="text-sm font-semibold mt-2 mb-1" style={{ color: 'var(--foreground)' }} {...p} />,
  p: (p: React.ComponentProps<'p'>) => <p className="text-sm leading-relaxed my-1.5" style={{ color: 'var(--foreground)' }} {...p} />,
  ul: (p: React.ComponentProps<'ul'>) => <ul className="list-disc ml-5 my-1.5 space-y-1 text-sm" style={{ color: 'var(--foreground)' }} {...p} />,
  ol: (p: React.ComponentProps<'ol'>) => <ol className="list-decimal ml-5 my-1.5 space-y-1 text-sm" style={{ color: 'var(--foreground)' }} {...p} />,
  strong: (p: React.ComponentProps<'strong'>) => <strong className="font-semibold" style={{ color: 'var(--foreground)' }} {...p} />,
}

export default function AdvisorPage() {
  const { mutate } = useSWRConfig()
  const { data: list } = useSWR<PortfoliosListResponse>('/portfolios', (p: string) => fetchAPI<PortfoliosListResponse>(p))
  const portfolios = useMemo(() => list?.portfolios ?? [], [list?.portfolios])

  const [step, setStep] = useState(0)
  const [portfolioId, setPortfolioId] = useState('')
  const [capital, setCapital] = useState('')
  const [withdraw, setWithdraw] = useState('')
  const [targetRoi, setTargetRoi] = useState('')
  const [risk, setRisk] = useState('moderate')
  const [horizon, setHorizon] = useState('12')

  const [result, setResult] = useState<AdvisorResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [applying, setApplying] = useState(false)
  const [applied, setApplied] = useState(false)

  // 持股來源：選現有投組 or 手動輸入
  const [source, setSource] = useState<'portfolio' | 'manual'>('portfolio')
  const [manualHoldings, setManualHoldings] = useState<{ stock_id: string; name: string; shares: number; cost_price: number }[]>([])
  // 手動新增列暫存（代號/中文名 → 股數 → 成本）
  const [addId, setAddId] = useState('')
  const [addName, setAddName] = useState('')
  const [addShares, setAddShares] = useState('')
  const [addCost, setAddCost] = useState('')
  const [addError, setAddError] = useState('')
  const [profileName, setProfileName] = useState('')
  const [savingProfile, setSavingProfile] = useState(false)
  const [saveMsg, setSaveMsg] = useState('')

  // 預設選第一個投組
  useEffect(() => {
    if (!portfolioId && portfolios.length > 0) setPortfolioId(portfolios[0].id)
  }, [portfolioId, portfolios])

  function addHolding() {
    const sid = addId.trim()
    const shares = Number(addShares) || 0
    if (!sid) { setAddError('請先選擇股票（輸入代號或中文名）'); return }
    if (shares <= 0) { setAddError('請輸入大於 0 的股數'); return }
    setAddError(''); setSaveMsg('')
    const cost = Number(addCost) || 0
    setManualHoldings((prev) => {
      // 同代號累加股數，成本價以新輸入覆蓋（若有填）
      const merged = [...prev]
      const idx = merged.findIndex((m) => m.stock_id === sid)
      if (idx >= 0) {
        merged[idx] = { ...merged[idx], shares: merged[idx].shares + shares, cost_price: cost || merged[idx].cost_price }
      } else {
        merged.push({ stock_id: sid, name: addName || '', shares, cost_price: cost })
      }
      return merged
    })
    setAddId(''); setAddName(''); setAddShares(''); setAddCost('')
  }

  function updateHolding(i: number, field: 'shares' | 'cost_price', value: string) {
    setManualHoldings((prev) => prev.map((h, idx) => idx === i ? { ...h, [field]: Number(value) || 0 } : h))
  }
  function removeHolding(i: number) {
    setManualHoldings((prev) => prev.filter((_, idx) => idx !== i))
  }

  async function saveAsProfile() {
    const name = profileName.trim()
    if (!name || manualHoldings.length === 0) return
    setSavingProfile(true); setSaveMsg('')
    try {
      // 建立投組（已存在則忽略 409），再寫入持股
      await fetchAPI('/portfolios', { method: 'POST', body: JSON.stringify({ name }) }).catch(() => {})
      await fetchAPI(`/portfolios/${encodeURIComponent(name)}`, {
        method: 'PUT',
        body: JSON.stringify({ holdings: manualHoldings.filter((h) => h.shares > 0).map((h) => ({ stock_id: h.stock_id, shares: Math.round(h.shares), cost_price: h.cost_price })) }),
      })
      await mutate('/portfolios')
      setPortfolioId(name); setSource('portfolio'); setSaveMsg(`✓ 已存成投組「${name}」，可直接分析或一鍵套用`)
    } catch (e) {
      setSaveMsg(e instanceof Error ? `儲存失敗：${e.message}` : '儲存失敗')
    } finally {
      setSavingProfile(false)
    }
  }

  async function runAnalysis() {
    setLoading(true); setError(''); setResult(null); setApplied(false)
    try {
      const useManual = source === 'manual' && manualHoldings.length > 0
      const body = {
        portfolio_id: useManual ? undefined : (portfolioId || undefined),
        holdings: useManual ? manualHoldings : undefined,
        capital_to_invest: Number(capital) || 0,
        withdraw_amount: Number(withdraw) || 0,
        target_roi: targetRoi ? Number(targetRoi) : undefined,
        risk_tolerance: risk,
        horizon_months: Number(horizon) || 12,
      }
      const res = await fetchAPI<AdvisorResult>('/advisor/analyze', {
        method: 'POST', body: JSON.stringify(body),
      }, 90000)
      setResult(res)
    } catch (e) {
      setError(e instanceof Error ? e.message : '分析失敗，請稍後再試（首次分析需運算全市場評分，較慢）')
    } finally {
      setLoading(false)
    }
  }

  async function applyToPortfolio() {
    if (!result || !portfolioId) return
    if (!window.confirm(`確定將建議套用到投組「${portfolioId}」？此動作會覆蓋現有持股。`)) return
    setApplying(true)
    try {
      await fetchAPI(`/portfolios/${portfolioId}`, {
        method: 'PUT',
        body: JSON.stringify({ holdings: result.proposed_holdings }),
      })
      await mutate(`/portfolios/${portfolioId}`)
      setApplied(true)
    } catch (e) {
      setError(e instanceof Error ? e.message : '套用失敗')
    } finally {
      setApplying(false)
    }
  }

  const steps = ['選擇持股', '資金規劃', '目標與風險']

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold flex items-center gap-2" style={{ color: 'var(--foreground)' }}>
          🧭 AI 投資顧問
        </h1>
        <p className="text-sm mt-1" style={{ color: 'var(--muted-foreground)' }}>
          資深操盤人風格：持股健檢 → 資金配置/再平衡 → 達標可行性，並可一鍵套用
        </p>
      </div>

      {/* Stepper */}
      <div className="flex items-center gap-2 mb-4">
        {steps.map((s, i) => (
          <div key={s} className="flex items-center gap-2">
            <span className="flex items-center gap-1.5 text-sm px-2.5 py-1 rounded-full" style={{
              background: i === step ? 'var(--primary)' : 'var(--secondary)',
              color: i === step ? 'var(--primary-foreground)' : 'var(--muted-foreground)',
            }}>
              <span className="font-mono">{i + 1}</span>{s}
            </span>
            {i < steps.length - 1 && <span style={{ color: 'var(--border)' }}>›</span>}
          </div>
        ))}
      </div>

      {/* Wizard form */}
      <div className="rounded-lg p-5 mb-6" style={card}>
        {step === 0 && (
          <div className="space-y-3 max-w-md">
            {/* 持股來源切換 */}
            <div className="flex gap-2">
              {([['portfolio', '選現有投組'], ['manual', '✏️ 手動輸入持股']] as const).map(([k, lbl]) => (
                <button key={k} onClick={() => setSource(k)}
                  className="px-3 h-9 rounded-md text-sm" style={{
                    background: source === k ? 'var(--primary)' : 'var(--secondary)',
                    color: source === k ? 'var(--primary-foreground)' : 'var(--muted-foreground)',
                    border: '1px solid var(--border)',
                  }}>{lbl}</button>
              ))}
            </div>

            {source === 'portfolio' ? (
              <>
                <label className="block text-sm" style={{ color: 'var(--muted-foreground)' }}>選擇要分析的投資組合</label>
                {portfolios.length > 0 ? (
                  <select value={portfolioId} onChange={(e) => setPortfolioId(e.target.value)}
                    className="w-full h-10 px-3 rounded-md text-sm outline-none" style={inputStyle}>
                    {portfolios.map((p) => <option key={p.id} value={p.id}>{p.id}（{p.holdings_count} 檔）</option>)}
                  </select>
                ) : (
                  <p className="text-sm" style={{ color: 'var(--muted-foreground)' }}>
                    尚無投資組合。可改用「手動輸入持股」，或直接輸入可投入資金做純新資金配置。
                  </p>
                )}
                <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>顧問會先對所選投組做量化健檢，再依你的資金與目標給建議。</p>
              </>
            ) : (
              <div className="space-y-3">
                <label className="block text-sm" style={{ color: 'var(--muted-foreground)' }}>逐筆輸入持股：搜尋代號或中文名（如 2330 或 台積電），填股數與成本價後按「新增」</label>
                <div className="grid grid-cols-[1fr_82px_82px_auto] gap-2 items-start">
                  <StockInput
                    value={addId}
                    onChange={setAddId}
                    onSelectResult={(r) => { setAddId(r.stock_id); setAddName(r.name) }}
                    placeholder="代號或中文名，例：2330 / 台積電"
                  />
                  <input type="number" min="0" value={addShares} onChange={(e) => setAddShares(e.target.value)} placeholder="股數"
                    onKeyDown={(e) => { if (e.key === 'Enter') addHolding() }}
                    className="h-10 px-2 rounded-md text-sm text-right outline-none num" style={inputStyle} />
                  <input type="number" min="0" value={addCost} onChange={(e) => setAddCost(e.target.value)} placeholder="成本價"
                    onKeyDown={(e) => { if (e.key === 'Enter') addHolding() }}
                    className="h-10 px-2 rounded-md text-sm text-right outline-none num" style={inputStyle} />
                  <button onClick={addHolding}
                    className="h-10 px-4 rounded-md text-sm font-medium shrink-0" style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}>新增</button>
                </div>
                {addError && <p className="text-sm" style={{ color: 'var(--stock-up)' }}>{addError}</p>}

                {manualHoldings.length > 0 && (
                  <>
                    <div className="rounded-md overflow-hidden" style={{ border: '1px solid var(--border)' }}>
                      <div className="grid grid-cols-[1fr_90px_90px_32px] gap-2 px-3 py-1.5 text-xs" style={{ background: 'var(--secondary)', color: 'var(--muted-foreground)' }}>
                        <span>代號 / 名稱</span><span className="text-right">股數</span><span className="text-right">成本價</span><span></span>
                      </div>
                      {manualHoldings.map((h, i) => (
                        <div key={`${h.stock_id}-${i}`} className="grid grid-cols-[1fr_90px_90px_32px] gap-2 px-3 py-1.5 items-center" style={{ borderTop: '1px solid var(--border)' }}>
                          <span className="text-sm truncate"><span className="font-mono" style={{ color: 'var(--primary)' }}>{h.stock_id}</span> <span style={{ color: 'var(--muted-foreground)' }}>{h.name}</span></span>
                          <input type="number" min="0" value={h.shares} onChange={(e) => updateHolding(i, 'shares', e.target.value)}
                            className="h-8 px-2 rounded text-sm text-right num" style={inputStyle} />
                          <input type="number" min="0" value={h.cost_price} onChange={(e) => updateHolding(i, 'cost_price', e.target.value)}
                            className="h-8 px-2 rounded text-sm text-right num" style={inputStyle} />
                          <button onClick={() => removeHolding(i)} title="移除" className="text-sm" style={{ color: 'var(--muted-foreground)' }}>✕</button>
                        </div>
                      ))}
                    </div>
                    <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>可直接修改股數/成本價、移除錯誤列。共 {manualHoldings.length} 檔。</p>

                    {/* 存成 profile（投組） */}
                    <div className="flex items-center gap-2 pt-1">
                      <input value={profileName} onChange={(e) => setProfileName(e.target.value)} placeholder="投組名稱（如 我的持股）"
                        className="flex-1 h-9 px-3 rounded-md text-sm outline-none" style={inputStyle} />
                      <button onClick={saveAsProfile} disabled={savingProfile || !profileName.trim()}
                        className="px-4 h-9 rounded-md text-sm font-medium disabled:opacity-50 shrink-0" style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}>
                        {savingProfile ? '儲存中…' : '💾 存成投組'}
                      </button>
                    </div>
                    {saveMsg && <p className="text-xs" style={{ color: saveMsg.startsWith('✓') ? 'var(--stock-down)' : 'var(--stock-up)' }}>{saveMsg}</p>}
                  </>
                )}
                <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>逐筆新增持股即可直接分析；存成投組後即可「一鍵套用」並永久保存。成本價可留空（僅影響損益估算）。</p>
              </div>
            )}
          </div>
        )}

        {step === 1 && (
          <div className="space-y-4 max-w-md">
            <div>
              <label className="block text-sm mb-1" style={{ color: 'var(--muted-foreground)' }}>想投入的新資金（元）</label>
              <input type="number" min="0" value={capital} onChange={(e) => setCapital(e.target.value)} placeholder="例如 500000"
                className="w-full h-10 px-3 rounded-md text-sm outline-none num" style={inputStyle} />
            </div>
            <div>
              <label className="block text-sm mb-1" style={{ color: 'var(--muted-foreground)' }}>想拿回的資金（元）</label>
              <input type="number" min="0" value={withdraw} onChange={(e) => setWithdraw(e.target.value)} placeholder="例如 0"
                className="w-full h-10 px-3 rounded-md text-sm outline-none num" style={inputStyle} />
              <p className="text-xs mt-1" style={{ color: 'var(--muted-foreground)' }}>顧問會優先賣出評分較低的持股來套現。</p>
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="space-y-4 max-w-md">
            <div>
              <label className="block text-sm mb-1" style={{ color: 'var(--muted-foreground)' }}>目標年化報酬率（%）</label>
              <input type="number" value={targetRoi} onChange={(e) => setTargetRoi(e.target.value)} placeholder="例如 15"
                className="w-full h-10 px-3 rounded-md text-sm outline-none num" style={inputStyle} />
            </div>
            <div>
              <label className="block text-sm mb-1" style={{ color: 'var(--muted-foreground)' }}>風險偏好</label>
              <select value={risk} onChange={(e) => setRisk(e.target.value)}
                className="w-full h-10 px-3 rounded-md text-sm outline-none" style={inputStyle}>
                {RISK_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm mb-1" style={{ color: 'var(--muted-foreground)' }}>投資期限（月）</label>
              <input type="number" min="1" value={horizon} onChange={(e) => setHorizon(e.target.value)}
                className="w-full h-10 px-3 rounded-md text-sm outline-none num" style={inputStyle} />
            </div>
          </div>
        )}

        {/* nav buttons */}
        <div className="flex items-center gap-2 mt-5">
          {step > 0 && (
            <button onClick={() => setStep(step - 1)} className="px-4 h-9 rounded-md text-sm" style={{ background: 'var(--secondary)', color: 'var(--foreground)', border: '1px solid var(--border)' }}>
              上一步
            </button>
          )}
          {step < 2 ? (
            <button onClick={() => setStep(step + 1)} className="px-4 h-9 rounded-md text-sm font-medium" style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}>
              下一步
            </button>
          ) : (
            <button onClick={runAnalysis} disabled={loading} className="px-5 h-9 rounded-md text-sm font-medium disabled:opacity-50" style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}>
              {loading ? '分析中…（首次較慢）' : '🔍 開始分析'}
            </button>
          )}
        </div>
      </div>

      {error && <EmptyState title="分析發生問題" description={error} icon="!" />}

      {/* Report */}
      {result && (
        <div className="space-y-6">
          {/* 健檢 */}
          <section>
            <h2 className="text-sm font-semibold mb-3" style={{ color: 'var(--foreground)' }}>📋 持股健檢</h2>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
              <KpiCard title="總市值" value={formatCurrency(result.health.total_value)} />
              <KpiCard title="平均評分" value={String(result.health.avg_score)} accentColor={ratingColor(result.health.avg_score >= 70 ? 'B' : 'C')} />
              <KpiCard title="集中度" value={result.health.concentration} subValue={`最大權重 ${result.health.top_weight}%`} />
              <KpiCard title="持股檔數" value={String(result.health.holdings.length)} />
            </div>
            <div className="rounded-lg overflow-x-auto" style={card}>
              <table className="w-full text-sm">
                <thead><tr style={{ borderBottom: '1px solid var(--border)' }}>
                  {['代號', '名稱', '權重', '評分', '評級', '市值'].map((h) => <th key={h} className="text-left px-3 py-2 font-medium" style={{ color: 'var(--muted-foreground)' }}>{h}</th>)}
                </tr></thead>
                <tbody>
                  {result.health.holdings.map((e) => (
                    <tr key={e.stock_id} style={{ borderBottom: '1px solid var(--border)' }}>
                      <td className="px-3 py-2 font-mono" style={{ color: 'var(--primary)' }}>{e.stock_id}</td>
                      <td className="px-3 py-2" style={{ color: 'var(--foreground)' }}>{e.name || '—'}</td>
                      <td className="px-3 py-2 num" style={{ color: 'var(--foreground)' }}>{e.weight}%</td>
                      <td className="px-3 py-2 num" style={{ color: 'var(--foreground)' }}>{e.score ?? '—'}</td>
                      <td className="px-3 py-2 font-semibold" style={{ color: ratingColor(e.rating) }}>{e.rating}</td>
                      <td className="px-3 py-2 num" style={{ color: 'var(--foreground)' }}>{formatCurrency(e.value)}</td>
                    </tr>
                  ))}
                  {result.health.holdings.length === 0 && (
                    <tr><td colSpan={6} className="px-3 py-4 text-center" style={{ color: 'var(--muted-foreground)' }}>無持股（純新資金配置）</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </section>

          {/* 配置/再平衡 */}
          <section className="grid md:grid-cols-2 gap-4">
            <div className="rounded-lg p-4" style={card}>
              <h3 className="text-sm font-semibold mb-2" style={{ color: 'var(--stock-up)' }}>🟢 建議買進（部署 {formatCurrency(result.plan.deployed)}）</h3>
              {result.plan.buys.length ? result.plan.buys.map((b) => (
                <div key={b.stock_id} className="py-1.5 text-sm" style={{ borderBottom: '1px solid var(--border)' }}>
                  <div className="flex justify-between"><span><span className="font-mono" style={{ color: 'var(--primary)' }}>{b.stock_id}</span> {b.name}</span>
                    <span className="num" style={{ color: 'var(--foreground)' }}>{formatCurrency(b.amount)}</span></div>
                  <div className="text-xs" style={{ color: 'var(--muted-foreground)' }}>{b.reason}</div>
                </div>
              )) : <p className="text-sm" style={{ color: 'var(--muted-foreground)' }}>無（未投入新資金）</p>}
            </div>
            <div className="rounded-lg p-4" style={card}>
              <h3 className="text-sm font-semibold mb-2" style={{ color: 'var(--stock-down)' }}>🔻 建議賣出（套現 {formatCurrency(result.plan.freed_cash)}）</h3>
              {result.plan.sells.length ? result.plan.sells.map((s) => (
                <div key={s.stock_id} className="py-1.5 text-sm" style={{ borderBottom: '1px solid var(--border)' }}>
                  <div className="flex justify-between"><span><span className="font-mono" style={{ color: 'var(--primary)' }}>{s.stock_id}</span> {s.name}</span>
                    <span className="num" style={{ color: 'var(--foreground)' }}>{formatCurrency(s.amount)}</span></div>
                  <div className="text-xs" style={{ color: 'var(--muted-foreground)' }}>{s.reason}</div>
                </div>
              )) : <p className="text-sm" style={{ color: 'var(--muted-foreground)' }}>無（未要求拿回資金）</p>}
            </div>
          </section>

          {/* 可行性 */}
          {result.feasibility && (
            <section className="rounded-lg p-4" style={card}>
              <h3 className="text-sm font-semibold mb-2" style={{ color: 'var(--foreground)' }}>🎯 達標可行性</h3>
              <div className="flex items-center gap-4 flex-wrap">
                <span className="text-2xl font-bold num" style={{ color: verdictColor(result.feasibility.verdict) }}>{result.feasibility.verdict}</span>
                <span className="text-sm" style={{ color: 'var(--muted-foreground)' }}>
                  目標 <b style={{ color: 'var(--foreground)' }}>{result.feasibility.target_roi}%</b> · 推估年化 <b style={{ color: getChangeColorVar(result.feasibility.estimated_annual_return) }}>{formatPercent(result.feasibility.estimated_annual_return)}</b>
                </span>
              </div>
              <p className="text-xs mt-2" style={{ color: 'var(--muted-foreground)' }}>{result.feasibility.note}</p>
            </section>
          )}

          {/* AI 敘述 */}
          {result.narrative ? (
            <section className="rounded-lg p-4" style={card}>
              <h3 className="text-sm font-semibold mb-2" style={{ color: 'var(--foreground)' }}>🧠 操盤人觀點</h3>
              <ReactMarkdown remarkPlugins={[remarkGfm]} components={MD}>{result.narrative}</ReactMarkdown>
            </section>
          ) : result.narrative_error ? (
            <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>（AI 敘述未生成：{result.narrative_error}）</p>
          ) : null}

          {/* 套用 */}
          <section className="rounded-lg p-4 flex items-center justify-between gap-3" style={card}>
            <div className="text-sm" style={{ color: 'var(--muted-foreground)' }}>
              套用後投組將更新為建議配置（{result.proposed_holdings.length} 檔）。{applied && <span style={{ color: 'var(--stock-down)' }}> ✓ 已套用</span>}
            </div>
            <button onClick={applyToPortfolio} disabled={applying || applied || !portfolioId} className="px-5 h-9 rounded-md text-sm font-medium disabled:opacity-50 shrink-0" style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}>
              {applying ? '套用中…' : applied ? '已套用' : '⚡ 一鍵套用到投組'}
            </button>
          </section>

          <p className="text-xs text-center" style={{ color: 'var(--muted-foreground)' }}>
            本分析為量化推估 + AI 輔助參考，不構成投資建議；投資有風險，請自行評估。
          </p>
        </div>
      )}
    </div>
  )
}
