'use client'

import { useState } from 'react'
import useSWR, { useSWRConfig } from 'swr'
import { fetchAPI } from '@/lib/api/client'
import { Alert } from '@/lib/types'
import { Switch } from '@/components/ui/switch'

const SWR_KEY = '/alerts'

// API 回傳 { total, alerts: [...] }
interface AlertsResponse {
  total: number
  alerts: Alert[]
}

interface AlertTypeOption {
  type: Alert['type']
  label: string
  unit: string
  default_value: number
}

interface AlertTypesResponse {
  types: AlertTypeOption[]
}

interface SmartAlert {
  stock_id: string
  name?: string
  severity: 'high' | 'medium' | string
  latest_price: number
  change_pct: number
  score?: number | null
  reasons: string[]
}

interface SmartAlertsResponse {
  total: number
  alerts: SmartAlert[]
}

type RuleMetric = 'price' | 'change_pct' | 'rsi' | 'volume_ratio'
type RuleOperator = 'gt' | 'gte' | 'lt' | 'lte' | 'eq'

interface AlertRule {
  id: string
  name: string
  match: 'all' | 'any'
  target: { stockIds: string[]; watchlistId?: string }
  conditions: Array<{
    field: RuleMetric
    operator: RuleOperator
    value: number
  }>
  frequency: 'once' | 'repeating'
  cooldownMinutes: number
  channels: Array<'telegram' | 'email'>
  enabled: boolean
  lastTriggeredAt?: string
}

interface AlertHit {
  id: string
  ruleId: string
  ruleName: string
  stockId: string
  triggeredAt: string
}

interface AlertRulesResponse {
  total: number
  rules: AlertRule[]
}

interface AlertHitsResponse {
  total: number
  hits: AlertHit[]
}

const RULES_KEY = '/alerts/rules'
const HITS_KEY = '/alerts/hits?limit=20'
const METRIC_LABELS: Record<RuleMetric, string> = {
  price: '現價',
  change_pct: '當日漲跌 %',
  rsi: 'RSI(14)',
  volume_ratio: '成交量倍數',
}
const OPERATOR_LABELS: Record<RuleOperator, string> = {
  gt: '大於',
  gte: '大於等於',
  lt: '小於',
  lte: '小於等於',
  eq: '等於',
}

const FALLBACK_ALERT_TYPES: AlertTypeOption[] = [
  { type: 'price_above', label: '價格高於', unit: '元', default_value: 600 },
  { type: 'price_below', label: '價格低於', unit: '元', default_value: 500 },
  { type: 'rsi_above', label: 'RSI 高於', unit: '', default_value: 70 },
  { type: 'rsi_below', label: 'RSI 低於', unit: '', default_value: 30 },
  { type: 'volume_spike', label: '爆量倍數', unit: '倍', default_value: 2 },
  { type: 'new_high', label: '創 N 日新高', unit: '日', default_value: 20 },
  { type: 'new_low', label: '創 N 日新低', unit: '日', default_value: 20 },
]

export default function AlertsPage() {
  const { mutate } = useSWRConfig()
  const { data: alertsData, isLoading, error } = useSWR<AlertsResponse>(SWR_KEY, fetchAPI)
  const { data: typesData } = useSWR<AlertTypesResponse>('/alerts/types', fetchAPI)
  const { data: smartData } = useSWR<SmartAlertsResponse>('/alerts/smart-preview?top_n=8', fetchAPI)
  const { data: rulesData } = useSWR<AlertRulesResponse>(RULES_KEY, fetchAPI)
  const { data: hitsData } = useSWR<AlertHitsResponse>(HITS_KEY, fetchAPI)
  const alerts = alertsData?.alerts
  const alertTypes = typesData?.types ?? FALLBACK_ALERT_TYPES
  const [dialogOpen, setDialogOpen] = useState(false)
  const [deleteId, setDeleteId] = useState<string | null>(null)
  const [form, setForm] = useState({
    code: '',
    type: 'price_above' as Alert['type'],
    value: '',
  })
  const [saving, setSaving] = useState(false)
  const [actionError, setActionError] = useState('')
  const [ruleDialogOpen, setRuleDialogOpen] = useState(false)
  const [evaluating, setEvaluating] = useState(false)
  const [ruleForm, setRuleForm] = useState({
    name: '',
    code: '',
    match: 'all' as 'all' | 'any',
    field1: 'price' as RuleMetric,
    operator1: 'gt' as RuleOperator,
    value1: '',
    field2: 'rsi' as RuleMetric,
    operator2: 'gt' as RuleOperator,
    value2: '',
    frequency: 'repeating' as 'once' | 'repeating',
    cooldownMinutes: 60,
    telegram: false,
    email: false,
  })

  const handleCreate = async () => {
    if (!form.code.trim() || !form.value) return
    setSaving(true)
    setActionError('')
    try {
      await fetchAPI(SWR_KEY, {
        method: 'POST',
        body: JSON.stringify({
          stock_id: form.code.toUpperCase(),
          type: form.type,
          value: Number(form.value),
        }),
      })
      await mutate(SWR_KEY)
      setDialogOpen(false)
      setForm({ code: '', type: 'price_above', value: '' })
    } catch {
      setActionError('警報建立失敗，請稍後再試')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id: string) => {
    setActionError('')
    try {
      await fetchAPI(`${SWR_KEY}/${id}`, { method: 'DELETE' })
      await mutate(SWR_KEY)
      setDeleteId(null)
    } catch {
      setActionError('警報刪除失敗，請稍後再試')
    }
  }

  const handleToggle = async (alert: Alert) => {
    setActionError('')
    try {
      await fetchAPI(`${SWR_KEY}/${alert.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ enabled: !alert.enabled }),
      })
      await mutate(SWR_KEY)
    } catch {
      setActionError('警報狀態更新失敗，請稍後再試')
    }
  }

  const handleCreateRule = async () => {
    if (!ruleForm.name.trim() || !ruleForm.code.trim() || ruleForm.value1 === '') return
    const conditions = [
      {
        field: ruleForm.field1,
        operator: ruleForm.operator1,
        value: Number(ruleForm.value1),
      },
    ]
    if (ruleForm.value2 !== '') {
      conditions.push({
        field: ruleForm.field2,
        operator: ruleForm.operator2,
        value: Number(ruleForm.value2),
      })
    }
    setSaving(true)
    setActionError('')
    try {
      await fetchAPI(RULES_KEY, {
        method: 'POST',
        body: JSON.stringify({
          name: ruleForm.name.trim(),
          match: ruleForm.match,
          target: { stockIds: [ruleForm.code.trim().toUpperCase()] },
          conditions,
          frequency: ruleForm.frequency,
          cooldownMinutes: ruleForm.cooldownMinutes,
          channels: [
            ...(ruleForm.telegram ? ['telegram' as const] : []),
            ...(ruleForm.email ? ['email' as const] : []),
          ],
        }),
      })
      await mutate(RULES_KEY)
      setRuleDialogOpen(false)
      setRuleForm((previous) => ({
        ...previous,
        name: '',
        code: '',
        value1: '',
        value2: '',
      }))
    } catch {
      setActionError('規則建立失敗，請稍後再試')
    } finally {
      setSaving(false)
    }
  }

  const handleEvaluateRules = async () => {
    setEvaluating(true)
    setActionError('')
    try {
      await fetchAPI('/alerts/evaluate', {
        method: 'POST',
        body: JSON.stringify({ sendNotifications: false }),
      })
      await Promise.all([mutate(RULES_KEY), mutate(HITS_KEY)])
    } catch {
      setActionError('規則評估失敗，請稍後再試')
    } finally {
      setEvaluating(false)
    }
  }

  const handleToggleRule = async (rule: AlertRule) => {
    setActionError('')
    try {
      await fetchAPI(`${RULES_KEY}/${rule.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ enabled: !rule.enabled }),
      })
      await mutate(RULES_KEY)
    } catch {
      setActionError('規則狀態更新失敗，請稍後再試')
    }
  }

  const handleDeleteRule = async (ruleId: string) => {
    setActionError('')
    try {
      await fetchAPI(`${RULES_KEY}/${ruleId}`, { method: 'DELETE' })
      await mutate(RULES_KEY)
    } catch {
      setActionError('規則刪除失敗，請稍後再試')
    }
  }

  const activeCount = alerts?.filter(a => a.enabled && !a.triggered).length ?? 0
  const triggeredCount = alerts?.filter(a => a.triggered).length ?? 0

  return (
    <div>
      <div className="mb-6 flex justify-between items-start">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: 'var(--foreground)' }}>Alerts 2.0</h1>
          <p className="text-sm mt-1" style={{ color: 'var(--muted-foreground)' }}>多條件規則、冷卻時間與命中歷史</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={handleEvaluateRules}
            disabled={evaluating}
            className="h-9 px-4 rounded-md text-sm font-medium disabled:opacity-60"
            style={{ background: 'var(--secondary)', color: 'var(--foreground)' }}
          >
            {evaluating ? '評估中…' : '立即評估'}
          </button>
          <button
            onClick={() => setRuleDialogOpen(true)}
            className="h-9 px-4 rounded-md text-sm font-medium"
            style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}
          >
            新增規則
          </button>
        </div>
      </div>

      {actionError && (
        <p className="mb-4 text-sm" role="alert" style={{ color: 'var(--destructive)' }}>{actionError}</p>
      )}
      {error && alertsData && (
        <p className="mb-4 text-sm" role="alert" style={{ color: 'var(--destructive)' }}>警報更新失敗，目前顯示上次成功載入的快取。</p>
      )}

      <div className="grid lg:grid-cols-[2fr_1fr] gap-4 mb-6">
        <section className="rounded-lg p-4" style={{ background: 'var(--card)', border: '1px solid var(--border)' }}>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold" style={{ color: 'var(--foreground)' }}>規則</h2>
            <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>{rulesData?.total ?? 0} 組</span>
          </div>
          <div className="space-y-2">
            {rulesData?.rules.length ? rulesData.rules.map((rule) => (
              <div key={rule.id} className="rounded-md p-3 flex items-start gap-3" style={{ background: 'var(--secondary)' }}>
                <Switch checked={rule.enabled} onCheckedChange={() => handleToggleRule(rule)} aria-label={`切換 ${rule.name}`} />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <p className="font-medium text-sm" style={{ color: 'var(--foreground)' }}>{rule.name}</p>
                    <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>{rule.match === 'all' ? '全部符合' : '任一符合'}</span>
                  </div>
                  <p className="text-xs mt-1" style={{ color: 'var(--muted-foreground)' }}>
                    {rule.target.stockIds.join(', ') || rule.target.watchlistId} · {rule.conditions.map((condition) => (
                      `${METRIC_LABELS[condition.field]}${OPERATOR_LABELS[condition.operator]} ${condition.value}`
                    )).join(rule.match === 'all' ? ' 且 ' : ' 或 ')}
                  </p>
                  <p className="text-xs mt-1" style={{ color: 'var(--muted-foreground)' }}>
                    {rule.frequency === 'once' ? '僅一次' : `冷卻 ${rule.cooldownMinutes} 分鐘`}
                    {rule.channels.length ? ` · ${rule.channels.join(' / ')}` : ' · 僅記錄'}
                  </p>
                </div>
                <button onClick={() => handleDeleteRule(rule.id)} className="text-xs" style={{ color: 'var(--destructive)' }}>刪除</button>
              </div>
            )) : (
              <p className="py-6 text-center text-sm" style={{ color: 'var(--muted-foreground)' }}>尚無 2.0 規則</p>
            )}
          </div>
        </section>
        <section className="rounded-lg p-4" style={{ background: 'var(--card)', border: '1px solid var(--border)' }}>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold" style={{ color: 'var(--foreground)' }}>最近命中</h2>
            <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>{hitsData?.total ?? 0} 筆</span>
          </div>
          <div className="space-y-2">
            {hitsData?.hits.slice(0, 8).map((hit) => (
              <div key={hit.id} className="border-b pb-2 last:border-0" style={{ borderColor: 'var(--border)' }}>
                <p className="text-sm font-medium" style={{ color: 'var(--foreground)' }}>{hit.stockId} · {hit.ruleName}</p>
                <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>{new Date(hit.triggeredAt).toLocaleString('zh-TW')}</p>
              </div>
            ))}
            {!hitsData?.hits.length && <p className="py-6 text-center text-sm" style={{ color: 'var(--muted-foreground)' }}>尚無命中紀錄</p>}
          </div>
        </section>
      </div>

      {/* 統計 */}
      {alerts && (
        <div className="grid grid-cols-3 gap-3 mb-6">
          <div className="rounded-lg p-4" style={{ background: 'var(--card)', border: '1px solid var(--border)' }}>
            <p className="text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>總警報數</p>
            <p className="text-2xl font-bold" style={{ color: 'var(--foreground)' }}>{alerts.length}</p>
          </div>
          <div className="rounded-lg p-4" style={{ background: 'var(--card)', border: '1px solid var(--border)' }}>
            <p className="text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>監控中</p>
            <p className="text-2xl font-bold" style={{ color: 'var(--primary)' }}>{activeCount}</p>
          </div>
          <div className="rounded-lg p-4" style={{ background: 'var(--card)', border: '1px solid var(--border)' }}>
            <p className="text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>已觸發</p>
            <p className="text-2xl font-bold" style={{ color: 'var(--destructive)' }}>{triggeredCount}</p>
          </div>
        </div>
      )}

      {smartData?.alerts?.length ? (
        <div
          className="rounded-lg p-4 mb-6"
          style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
        >
          <div className="flex items-center justify-between mb-3">
            <div>
              <h2 className="text-sm font-semibold" style={{ color: 'var(--foreground)' }}>智慧警報建議</h2>
              <p className="text-xs mt-0.5" style={{ color: 'var(--muted-foreground)' }}>
                量化評分、突破、跌破與爆量訊號
              </p>
            </div>
            <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>{smartData.total} 筆</span>
          </div>
          <div className="grid md:grid-cols-2 gap-2">
            {smartData.alerts.map((item) => (
              <div key={`${item.stock_id}-${item.reasons.join(',')}`} className="rounded-md p-3" style={{ background: 'var(--secondary)' }}>
                <div className="flex items-center justify-between gap-2 mb-1">
                  <p className="font-semibold text-sm" style={{ color: 'var(--primary)' }}>
                    {item.stock_id} {item.name ?? ''}
                  </p>
                  <span className="text-xs" style={{ color: item.severity === 'high' ? 'var(--destructive)' : 'var(--muted-foreground)' }}>
                    {item.severity === 'high' ? '高' : '中'}
                  </span>
                </div>
                <p className="text-xs mb-2" style={{ color: 'var(--muted-foreground)' }}>
                  現價 {item.latest_price.toFixed(2)} / 評分 {item.score?.toFixed(1) ?? '—'}
                </p>
                <p className="text-xs" style={{ color: 'var(--foreground)' }}>{item.reasons[0]}</p>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {/* 警報列表 */}
      {error && !alertsData ? (
        <div className="rounded-lg p-6 text-center" style={{ background: 'var(--card)', border: '1px solid var(--border)' }}>
          <p style={{ color: 'var(--destructive)' }}>資料載入失敗</p>
          <button type="button" onClick={() => mutate(SWR_KEY)} className="mt-3 text-sm font-medium" style={{ color: 'var(--primary)' }}>重新載入</button>
        </div>
      ) : isLoading ? (
        <div className="space-y-2">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-16 rounded-lg animate-pulse" style={{ background: 'var(--card)' }} />
          ))}
        </div>
      ) : alerts && alerts.length > 0 ? (
        <div className="space-y-2">
          {alerts.map((alert) => {
            const typeInfo = alertTypes.find(t => t.type === alert.type)
            const statusColor = alert.triggered
              ? 'var(--destructive)'
              : alert.enabled
              ? 'var(--stock-down)'
              : 'var(--muted-foreground)'
            const statusLabel = alert.triggered ? '已觸發' : alert.enabled ? '監控中' : '已停用'

            return (
              <div
                key={alert.id}
                className="rounded-lg p-4 flex items-center gap-4"
                style={{
                  background: 'var(--card)',
                  border: `1px solid ${alert.triggered ? 'var(--destructive)' : 'var(--border)'}`,
                }}
              >
                {/* 開關 */}
                <Switch
                  checked={alert.enabled}
                  onCheckedChange={() => handleToggle(alert)}
                  disabled={alert.triggered}
                  aria-label={`切換 ${alert.code ?? alert.stock_id} 警報`}
                  className="flex-shrink-0"
                />

                {/* 代號 */}
                <div className="flex-shrink-0">
                  <p className="font-semibold" style={{ color: 'var(--primary)' }}>{alert.stock_id ?? alert.code}</p>
                  <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>{alert.name}</p>
                </div>

                {/* 條件 */}
                <div className="flex-1">
                  <p className="text-sm" style={{ color: 'var(--foreground)' }}>
                    {typeInfo?.label ?? alert.type}
                    <span className="font-semibold ml-1">
                      {alert.value} {typeInfo?.unit}
                    </span>
                  </p>
                  <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
                    建立於 {(alert.created_at ?? alert.createdAt ?? '').slice(0, 10)}
                  </p>
                </div>

                {/* 狀態 */}
                <span
                  className="px-2 py-1 rounded-full text-xs font-medium flex-shrink-0"
                  style={{ background: statusColor + '22', color: statusColor }}
                >
                  {statusLabel}
                </span>

                {/* 刪除 */}
                <button
                  onClick={() => setDeleteId(alert.id)}
                  className="text-xs px-2 py-1 rounded flex-shrink-0"
                  style={{ color: 'var(--destructive)' }}
                >
                  刪除
                </button>
              </div>
            )
          })}
        </div>
      ) : (
        <div
          className="rounded-lg p-12 text-center"
          style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
        >
          <p className="text-lg mb-2" style={{ color: 'var(--muted-foreground)' }}>尚無警報設定</p>
          <p className="text-sm" style={{ color: 'var(--muted-foreground)' }}>
            點擊新增警報，設定股價觸發條件
          </p>
        </div>
      )}

      {/* 新增 Dialog */}
      {ruleDialogOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: 'rgba(0,0,0,0.7)' }}>
          <div className="w-full max-w-2xl rounded-lg p-6" style={{ background: 'var(--card)', border: '1px solid var(--border)' }}>
            <h2 className="text-lg font-semibold mb-4" style={{ color: 'var(--foreground)' }}>新增 Alerts 2.0 規則</h2>
            <div className="grid md:grid-cols-2 gap-3">
              <input value={ruleForm.name} onChange={(event) => setRuleForm((value) => ({ ...value, name: event.target.value }))} placeholder="規則名稱" className="h-9 rounded-md border px-3 text-sm" style={{ background: 'var(--background)', borderColor: 'var(--border)' }} />
              <input value={ruleForm.code} onChange={(event) => setRuleForm((value) => ({ ...value, code: event.target.value.toUpperCase() }))} placeholder="股票代號，例如 2330" className="h-9 rounded-md border px-3 text-sm" style={{ background: 'var(--background)', borderColor: 'var(--border)' }} />
              {[1, 2].map((index) => {
                const fieldKey = `field${index}` as 'field1' | 'field2'
                const operatorKey = `operator${index}` as 'operator1' | 'operator2'
                const valueKey = `value${index}` as 'value1' | 'value2'
                return (
                  <div key={index} className="md:col-span-2 grid grid-cols-[1fr_1fr_1fr] gap-2">
                    <select value={ruleForm[fieldKey]} onChange={(event) => setRuleForm((value) => ({ ...value, [fieldKey]: event.target.value as RuleMetric }))} className="h-9 rounded-md border px-2 text-sm" style={{ background: 'var(--background)', borderColor: 'var(--border)' }}>
                      {Object.entries(METRIC_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                    </select>
                    <select value={ruleForm[operatorKey]} onChange={(event) => setRuleForm((value) => ({ ...value, [operatorKey]: event.target.value as RuleOperator }))} className="h-9 rounded-md border px-2 text-sm" style={{ background: 'var(--background)', borderColor: 'var(--border)' }}>
                      {Object.entries(OPERATOR_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                    </select>
                    <input type="number" value={ruleForm[valueKey]} onChange={(event) => setRuleForm((value) => ({ ...value, [valueKey]: event.target.value }))} placeholder={index === 1 ? '觸發值' : '第二條件（可留空）'} className="h-9 rounded-md border px-3 text-sm" style={{ background: 'var(--background)', borderColor: 'var(--border)' }} />
                  </div>
                )
              })}
              <select value={ruleForm.match} onChange={(event) => setRuleForm((value) => ({ ...value, match: event.target.value as 'all' | 'any' }))} className="h-9 rounded-md border px-2 text-sm" style={{ background: 'var(--background)', borderColor: 'var(--border)' }}>
                <option value="all">全部條件符合（AND）</option>
                <option value="any">任一條件符合（OR）</option>
              </select>
              <div className="flex items-center gap-2">
                <input type="number" min={0} value={ruleForm.cooldownMinutes} onChange={(event) => setRuleForm((value) => ({ ...value, cooldownMinutes: Number(event.target.value) }))} className="h-9 w-24 rounded-md border px-3 text-sm" style={{ background: 'var(--background)', borderColor: 'var(--border)' }} />
                <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>分鐘冷卻</span>
              </div>
              <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={ruleForm.telegram} onChange={(event) => setRuleForm((value) => ({ ...value, telegram: event.target.checked }))} /> Telegram</label>
              <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={ruleForm.email} onChange={(event) => setRuleForm((value) => ({ ...value, email: event.target.checked }))} /> Email</label>
            </div>
            <div className="mt-5 flex justify-end gap-2">
              <button onClick={() => setRuleDialogOpen(false)} className="h-9 px-4 rounded-md text-sm" style={{ background: 'var(--secondary)' }}>取消</button>
              <button onClick={handleCreateRule} disabled={saving} className="h-9 px-4 rounded-md text-sm disabled:opacity-60" style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}>{saving ? '儲存中…' : '建立規則'}</button>
            </div>
          </div>
        </div>
      )}

      {/* 舊版單一條件警報保留相容 */}
      {dialogOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: 'rgba(0,0,0,0.7)' }}>
          <div
            className="w-full max-w-md rounded-lg p-6"
            style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
          >
            <h2 className="text-lg font-semibold mb-4" style={{ color: 'var(--foreground)' }}>新增警報</h2>
            <div className="space-y-3">
              <div>
                <label className="block text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>股票代號</label>
                <input
                  type="text"
                  value={form.code}
                  onChange={(e) => setForm(p => ({ ...p, code: e.target.value.toUpperCase() }))}
                  placeholder="例：2330"
                  className="h-9 w-full rounded-md border px-3 text-sm"
                  style={{ background: 'var(--background)', border: '1px solid var(--border)', color: 'var(--foreground)' }}
                />
              </div>
              <div>
                <label className="block text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>警報類型</label>
                <select
                  value={form.type}
                  onChange={(e) => setForm(p => ({ ...p, type: e.target.value as Alert['type'] }))}
                  className="h-9 w-full rounded-md border px-3 text-sm"
                  style={{ background: 'var(--background)', border: '1px solid var(--border)', color: 'var(--foreground)' }}
                >
                  {alertTypes.map(t => (
                    <option key={t.type} value={t.type}>{t.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>
                  觸發值（{alertTypes.find(t => t.type === form.type)?.unit}）
                </label>
                <input
                  type="number"
                  value={form.value}
                  onChange={(e) => setForm(p => ({ ...p, value: e.target.value }))}
                  placeholder="例：600"
                  className="h-9 w-full rounded-md border px-3 text-sm"
                  style={{ background: 'var(--background)', border: '1px solid var(--border)', color: 'var(--foreground)' }}
                />
              </div>
              <div
                className="rounded-md p-3 text-sm"
                style={{ background: 'var(--secondary)', color: 'var(--muted-foreground)' }}
              >
                當 <span className="font-semibold" style={{ color: 'var(--foreground)' }}>{form.code || '[股票]'}</span>
                {' '}{alertTypes.find(t => t.type === form.type)?.label}
                {' '}<span className="font-semibold" style={{ color: 'var(--foreground)' }}>
                  {form.value || '[值]'} {alertTypes.find(t => t.type === form.type)?.unit}
                </span>
                {' '}時觸發警報
              </div>
            </div>
            <div className="mt-4 flex justify-end gap-2">
              <button
                onClick={() => setDialogOpen(false)}
                className="h-9 px-4 rounded-md text-sm"
                style={{ background: 'var(--secondary)', color: 'var(--foreground)' }}
              >
                取消
              </button>
              <button
                onClick={handleCreate}
                disabled={saving}
                className="h-9 px-4 rounded-md text-sm disabled:opacity-60"
                style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}
              >
                {saving ? '儲存中...' : '新增'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 刪除確認 */}
      {deleteId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: 'rgba(0,0,0,0.7)' }}>
          <div className="w-full max-w-sm rounded-lg p-6" style={{ background: 'var(--card)', border: '1px solid var(--border)' }}>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--foreground)' }}>確認刪除</h2>
            <p className="text-sm mb-4" style={{ color: 'var(--muted-foreground)' }}>確定要刪除此警報嗎？</p>
            <div className="flex justify-end gap-2">
              <button onClick={() => setDeleteId(null)} className="h-9 px-4 rounded-md text-sm" style={{ background: 'var(--secondary)', color: 'var(--foreground)' }}>取消</button>
              <button onClick={() => handleDelete(deleteId)} className="h-9 px-4 rounded-md text-sm" style={{ background: 'var(--destructive)', color: 'var(--destructive-foreground)' }}>刪除</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
