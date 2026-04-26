'use client'

import { useState } from 'react'
import useSWR, { mutate } from 'swr'
import { fetchAPI } from '@/lib/api/client'

interface Settings {
  telegram: {
    enabled: boolean
    botToken: string
    chatId: string
  }
  email: {
    enabled: boolean
    smtpHost: string
    smtpPort: number
    username: string
    password: string
    recipient: string
  }
  system: {
    dataUpdateInterval: number
    timezone: string
    autoBacktest: boolean
    marketOpenTime: string
    marketCloseTime: string
  }
}

interface SystemInfo {
  version: string
  apiVersion: string
  uptime: string
  dataLastUpdated: string
  stockCount: number
  dbSize: string
}

const SWR_KEY = '/settings'
const INFO_KEY = '/system/info'

export default function SettingsPage() {
  const { data: settings, isLoading } = useSWR<Settings>(SWR_KEY, fetchAPI)
  const { data: sysInfo } = useSWR<SystemInfo>(INFO_KEY, fetchAPI)

  const [form, setForm] = useState<Partial<Settings>>({})
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [testTgStatus, setTestTgStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle')

  const currentSettings = { ...settings, ...form }

  const updateTelegram = (key: string, value: string | boolean) => {
    setForm(prev => ({
      ...prev,
      telegram: { ...currentSettings?.telegram, ...prev.telegram, [key]: value } as Settings['telegram'],
    }))
  }

  const updateEmail = (key: string, value: string | number | boolean) => {
    setForm(prev => ({
      ...prev,
      email: { ...currentSettings?.email, ...prev.email, [key]: value } as Settings['email'],
    }))
  }

  const updateSystem = (key: string, value: string | number | boolean) => {
    setForm(prev => ({
      ...prev,
      system: { ...currentSettings?.system, ...prev.system, [key]: value } as Settings['system'],
    }))
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      await fetchAPI(SWR_KEY, {
        method: 'PUT',
        body: JSON.stringify({ ...settings, ...form }),
      })
      await mutate(SWR_KEY)
      setForm({})
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    } finally {
      setSaving(false)
    }
  }

  const handleTestTelegram = async () => {
    setTestTgStatus('loading')
    try {
      await fetchAPI('/settings/test-telegram', { method: 'POST' })
      setTestTgStatus('success')
      setTimeout(() => setTestTgStatus('idle'), 3000)
    } catch {
      setTestTgStatus('error')
      setTimeout(() => setTestTgStatus('idle'), 3000)
    }
  }

  if (isLoading) {
    return (
      <div>
        <div className="mb-6">
          <h1 className="text-2xl font-bold" style={{ color: 'var(--foreground)' }}>系統設定</h1>
        </div>
        <div className="space-y-4">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-40 rounded-lg animate-pulse" style={{ background: 'var(--card)' }} />
          ))}
        </div>
      </div>
    )
  }

  const tg = currentSettings?.telegram
  const em = currentSettings?.email
  const sys = currentSettings?.system

  return (
    <div>
      <div className="mb-6 flex justify-between items-start">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: 'var(--foreground)' }}>系統設定</h1>
          <p className="text-sm mt-1" style={{ color: 'var(--muted-foreground)' }}>通知與系統參數配置</p>
        </div>
        <div className="flex items-center gap-2">
          {saved && (
            <span className="text-sm" style={{ color: 'var(--stock-down)' }}>已儲存</span>
          )}
          <button
            onClick={handleSave}
            disabled={saving}
            className="h-9 px-4 rounded-md text-sm font-medium disabled:opacity-60"
            style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}
          >
            {saving ? '儲存中...' : '儲存設定'}
          </button>
        </div>
      </div>

      <div className="space-y-4">
        {/* Telegram */}
        <div
          className="rounded-lg p-4"
          style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
        >
          <div className="flex justify-between items-center mb-4">
            <div>
              <h3 className="text-base font-semibold" style={{ color: 'var(--foreground)' }}>Telegram 通知</h3>
              <p className="text-xs mt-0.5" style={{ color: 'var(--muted-foreground)' }}>
                透過 Telegram Bot 接收股價警報通知
              </p>
            </div>
            <label className="flex items-center gap-2 cursor-pointer">
              <span className="text-sm" style={{ color: 'var(--muted-foreground)' }}>
                {tg?.enabled ? '已啟用' : '已停用'}
              </span>
              <button
                onClick={() => updateTelegram('enabled', !tg?.enabled)}
                className="relative w-10 h-5 rounded-full transition-colors"
                style={{ background: tg?.enabled ? 'var(--primary)' : 'var(--secondary)' }}
              >
                <span
                  className="absolute top-0.5 w-4 h-4 rounded-full bg-white transition-all"
                  style={{ left: tg?.enabled ? '22px' : '2px' }}
                />
              </button>
            </label>
          </div>
          {tg?.enabled && (
            <div className="space-y-3">
              <div>
                <label className="block text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>Bot Token</label>
                <input
                  type="password"
                  value={tg?.botToken ?? ''}
                  onChange={(e) => updateTelegram('botToken', e.target.value)}
                  placeholder="1234567890:ABC..."
                  className="h-9 w-full rounded-md border px-3 text-sm"
                  style={{ background: 'var(--background)', border: '1px solid var(--border)', color: 'var(--foreground)' }}
                />
              </div>
              <div>
                <label className="block text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>Chat ID</label>
                <input
                  type="text"
                  value={tg?.chatId ?? ''}
                  onChange={(e) => updateTelegram('chatId', e.target.value)}
                  placeholder="-1001234567890"
                  className="h-9 w-full rounded-md border px-3 text-sm"
                  style={{ background: 'var(--background)', border: '1px solid var(--border)', color: 'var(--foreground)' }}
                />
              </div>
              <button
                onClick={handleTestTelegram}
                disabled={testTgStatus === 'loading'}
                className="h-8 px-4 rounded-md text-sm font-medium disabled:opacity-60"
                style={{ background: 'var(--secondary)', color: 'var(--foreground)' }}
              >
                {testTgStatus === 'loading' ? '測試中...'
                  : testTgStatus === 'success' ? '傳送成功'
                  : testTgStatus === 'error' ? '傳送失敗'
                  : '測試傳送'}
              </button>
            </div>
          )}
        </div>

        {/* Email */}
        <div
          className="rounded-lg p-4"
          style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
        >
          <div className="flex justify-between items-center mb-4">
            <div>
              <h3 className="text-base font-semibold" style={{ color: 'var(--foreground)' }}>Email 通知</h3>
              <p className="text-xs mt-0.5" style={{ color: 'var(--muted-foreground)' }}>
                透過 SMTP 接收 Email 通知
              </p>
            </div>
            <button
              onClick={() => updateEmail('enabled', !em?.enabled)}
              className="relative w-10 h-5 rounded-full transition-colors"
              style={{ background: em?.enabled ? 'var(--primary)' : 'var(--secondary)' }}
            >
              <span
                className="absolute top-0.5 w-4 h-4 rounded-full bg-white transition-all"
                style={{ left: em?.enabled ? '22px' : '2px' }}
              />
            </button>
          </div>
          {em?.enabled && (
            <div className="grid grid-cols-2 gap-3">
              {[
                { key: 'smtpHost', label: 'SMTP 主機', placeholder: 'smtp.gmail.com', type: 'text' },
                { key: 'smtpPort', label: 'SMTP 埠', placeholder: '587', type: 'number' },
                { key: 'username', label: '帳號', placeholder: 'your@email.com', type: 'text' },
                { key: 'password', label: '密碼', placeholder: '••••••••', type: 'password' },
                { key: 'recipient', label: '收件人 Email', placeholder: 'alert@email.com', type: 'text' },
              ].map(({ key, label, placeholder, type }) => (
                <div key={key}>
                  <label className="block text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>{label}</label>
                  <input
                    type={type}
                    value={(em as unknown as Record<string, string | number>)[key]?.toString() ?? ''}
                    onChange={(e) => updateEmail(key, type === 'number' ? Number(e.target.value) : e.target.value)}
                    placeholder={placeholder}
                    className="h-9 w-full rounded-md border px-3 text-sm"
                    style={{ background: 'var(--background)', border: '1px solid var(--border)', color: 'var(--foreground)' }}
                  />
                </div>
              ))}
            </div>
          )}
        </div>

        {/* 系統設定 */}
        <div
          className="rounded-lg p-4"
          style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
        >
          <h3 className="text-base font-semibold mb-4" style={{ color: 'var(--foreground)' }}>系統參數</h3>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            <div>
              <label className="block text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>
                資料更新間隔（秒）
              </label>
              <input
                type="number"
                value={sys?.dataUpdateInterval ?? 30}
                onChange={(e) => updateSystem('dataUpdateInterval', Number(e.target.value))}
                className="h-9 w-full rounded-md border px-3 text-sm"
                style={{ background: 'var(--background)', border: '1px solid var(--border)', color: 'var(--foreground)' }}
              />
            </div>
            <div>
              <label className="block text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>時區</label>
              <select
                value={sys?.timezone ?? 'Asia/Taipei'}
                onChange={(e) => updateSystem('timezone', e.target.value)}
                className="h-9 w-full rounded-md border px-3 text-sm"
                style={{ background: 'var(--background)', border: '1px solid var(--border)', color: 'var(--foreground)' }}
              >
                <option value="Asia/Taipei">Asia/Taipei (UTC+8)</option>
                <option value="UTC">UTC</option>
              </select>
            </div>
            <div>
              <label className="block text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>市場開盤時間</label>
              <input
                type="time"
                value={sys?.marketOpenTime ?? '09:00'}
                onChange={(e) => updateSystem('marketOpenTime', e.target.value)}
                className="h-9 w-full rounded-md border px-3 text-sm"
                style={{ background: 'var(--background)', border: '1px solid var(--border)', color: 'var(--foreground)' }}
              />
            </div>
            <div>
              <label className="block text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>市場收盤時間</label>
              <input
                type="time"
                value={sys?.marketCloseTime ?? '13:30'}
                onChange={(e) => updateSystem('marketCloseTime', e.target.value)}
                className="h-9 w-full rounded-md border px-3 text-sm"
                style={{ background: 'var(--background)', border: '1px solid var(--border)', color: 'var(--foreground)' }}
              />
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={() => updateSystem('autoBacktest', !sys?.autoBacktest)}
                className="relative w-10 h-5 rounded-full transition-colors flex-shrink-0"
                style={{ background: sys?.autoBacktest ? 'var(--primary)' : 'var(--secondary)' }}
              >
                <span
                  className="absolute top-0.5 w-4 h-4 rounded-full bg-white transition-all"
                  style={{ left: sys?.autoBacktest ? '22px' : '2px' }}
                />
              </button>
              <span className="text-sm" style={{ color: 'var(--foreground)' }}>自動定期回測</span>
            </div>
          </div>
        </div>

        {/* 系統資訊 */}
        {sysInfo && (
          <div
            className="rounded-lg p-4"
            style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
          >
            <h3 className="text-base font-semibold mb-4" style={{ color: 'var(--foreground)' }}>系統資訊</h3>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
              {[
                { label: '前端版本', value: sysInfo.version },
                { label: 'API 版本', value: sysInfo.apiVersion },
                { label: '系統運行時間', value: sysInfo.uptime },
                { label: '資料最後更新', value: sysInfo.dataLastUpdated },
                { label: '股票數量', value: `${sysInfo.stockCount} 支` },
                { label: '資料庫大小', value: sysInfo.dbSize },
              ].map(({ label, value }) => (
                <div key={label} className="rounded-md p-3" style={{ background: 'var(--secondary)' }}>
                  <p className="text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>{label}</p>
                  <p className="text-sm font-medium" style={{ color: 'var(--foreground)' }}>{value}</p>
                </div>
              ))}
            </div>
          </div>
        )}
        {/* 版本記錄 */}
        <div
          className="rounded-lg p-4"
          style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
        >
          <div className="flex justify-between items-center mb-4">
            <div>
              <h3 className="text-base font-semibold" style={{ color: 'var(--foreground)' }}>版本記錄</h3>
              <p className="text-xs mt-0.5" style={{ color: 'var(--muted-foreground)' }}>系統更新歷程與變化</p>
            </div>
            <span
              className="px-3 py-1 rounded-full text-xs font-bold"
              style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}
            >
              v3.5.0
            </span>
          </div>

          <div className="space-y-0" style={{ maxHeight: 500, overflowY: 'auto' }}>
            {CHANGELOG.map((release, i) => (
              <div key={release.version} style={{ position: 'relative', paddingLeft: 24, paddingBottom: i < CHANGELOG.length - 1 ? 16 : 0 }}>
                {/* Timeline line */}
                {i < CHANGELOG.length - 1 && (
                  <div style={{ position: 'absolute', left: 7, top: 8, bottom: 0, width: 2, background: 'var(--border)' }} />
                )}
                {/* Timeline dot */}
                <div style={{
                  position: 'absolute', left: 2, top: 6,
                  width: 12, height: 12, borderRadius: '50%',
                  background: i === 0 ? 'var(--primary)' : 'var(--secondary)',
                  border: i === 0 ? 'none' : '2px solid var(--border)',
                }} />
                {/* Content */}
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-sm font-bold" style={{ color: i === 0 ? 'var(--primary)' : 'var(--foreground)' }}>
                      {release.version}
                    </span>
                    <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
                      {release.date}
                    </span>
                    {release.tag && (
                      <span
                        className="text-xs px-1.5 py-0.5 rounded"
                        style={{
                          background: release.tag === 'Major' ? 'rgba(59,130,246,0.15)' : release.tag === 'Feature' ? 'rgba(34,197,94,0.15)' : 'rgba(107,114,128,0.15)',
                          color: release.tag === 'Major' ? '#3b82f6' : release.tag === 'Feature' ? '#22c55e' : '#6b7280',
                        }}
                      >
                        {release.tag}
                      </span>
                    )}
                  </div>
                  <ul className="space-y-0.5">
                    {release.changes.map((change, j) => (
                      <li key={j} className="text-xs flex items-start gap-1.5" style={{ color: 'var(--muted-foreground)' }}>
                        <span style={{ color: 'var(--primary)', flexShrink: 0 }}>•</span>
                        {change}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Changelog Data                                                     */
/* ------------------------------------------------------------------ */

const CHANGELOG = [
  {
    version: 'v3.5.0',
    date: '2026-04-26',
    tag: 'Feature' as const,
    changes: [
      '功能新增：AI 操盤雷達，整合籌碼、營收、技術位置與出貨風險',
      '功能新增：主力吸籌偵測，辨識法人買超但股價尚未過熱的型態',
      '功能新增：營收爆發未反應清單，找出基本面轉強但短線漲幅有限的個股',
      '功能新增：出貨風險警報，提示高位法人轉賣、爆量收低與追價風險',
      '功能新增：進場等待區與每日觀察清單，提供觀察價、支撐、壓力與失效條件',
    ],
  },
  {
    version: 'v3.4.1',
    date: '2026-04-26',
    tag: 'Feature' as const,
    changes: [
      '功能新增：公司營運概況資料層，支援主要產品線、營收來源、業務範圍與產業別',
      '功能新增：個股頁新增公司營運概況卡，補足僅有技術數據時的基本面脈絡',
      '功能新增：新增 /stock/{id}/profile API，先讀本機補充資料，再嘗試公開資料來源自動補齊',
      '資料補充：友輝 4933 新增產品線與 113 年度增光膜內外銷營收結構',
    ],
  },
  {
    version: 'v3.4.0',
    date: '2026-04-26',
    tag: 'Feature' as const,
    changes: [
      '功能新增：Phase 2 評分變化歷史與升降級榜，追蹤量化分數趨勢',
      '功能新增：Phase 3 智慧警報 2.0，加入評分、突破、跌破與爆量建議',
      '功能新增：Phase 4 個股 AI 摘要，不依賴外部模型也能產生資料判讀',
      '功能新增：Phase 5 投資組合診斷，顯示集中度、產業配置、波動與回撤',
      '功能新增：Phase 6 產業輪動雷達，整合短中期動能與上漲廣度',
      '功能新增：Phase 7 自訂 Dashboard widget config API 與首屏摘要卡',
      '版本修正：警報前後端欄位契約對齊，補齊 PATCH 更新與支援類型清單',
    ],
  },
  {
    version: 'v3.3.0',
    date: '2026-04-26',
    tag: 'Feature' as const,
    changes: [
      '功能新增：公開工具目錄鏡像至前端 public/tool_catalog.json，方便外部 AI / app 直接讀取工具定義',
      '功能新增：新增 API router registration smoke test，保護 24 個核心 router 不會在重構時漏掛',
      '版本修正：README 與前端 README 更新為 FastAPI + Next.js + Streamlit 並存架構',
      '版本修正：Vercel 部署忽略規則補齊，排除後端、測試、快取與本機工具狀態',
      '版本修正：修復前端 lint warning，補齊股票搜尋 combobox ARIA 屬性',
      '版本修正：固定 Turbopack root，避免 Next.js build 誤判 workspace root',
      '版本修正：持倉總覽同步處理投資組合明細載入錯誤狀態',
    ],
  },
  {
    version: 'v3.2.0',
    date: '2026-03-27',
    tag: 'Feature' as const,
    changes: [
      'Claude AI 智慧分析上線（Anthropic API 整合）',
      'LSTM 趨勢預測修正：支援中文方向值（上漲/下跌/盤整）',
      '全站股票搜尋元件升級：50 筆結果 + 可滾動下拉 + 鍵盤導航',
      '個股分析頁面新增搜尋框，可直接切換股票',
      'Header 搜尋 bar 支援滾動選取',
      '選股篩選結果新增中文名稱欄位',
      '參數優化功能（Grid Search 均線交叉回測）',
      '財報分析 + 籌碼分析頁面重寫對齊 API',
      '版本記錄時間軸 UI',
    ],
  },
  {
    version: 'v3.1.0',
    date: '2026-03-27',
    tag: 'Feature' as const,
    changes: [
      '全部 24 頁面 API 欄位對齊修復',
      '盤後總覽：收盤指數修正 + 三大法人單位改為張',
      '資金流向：投信欄位修正（investment_trust）',
      '市場熱力圖改為 Bloomberg 風格層級式下鑽（產業→個股）',
      'AI 路由衝突修復（StrategyType Enum）',
      'SafeJSONResponse 全域防 NaN/inf 崩潰',
      '新聞 RSS 即時掃描 + 晨報整合新聞摘要',
      'API 效能優化：個股端點快取 + 啟動預熱 14 個 pickle',
    ],
  },
  {
    version: 'v3.0.0',
    date: '2026-03-27',
    tag: 'Major' as const,
    changes: [
      '全新 Next.js + React + Tailwind CSS 前端（取代 Streamlit）',
      '部署至 Vercel（前端）+ Railway（API 後端）',
      '新增 3 個 AI 模型：XGBoost 因子選股、LSTM 趨勢預測、Claude 智慧分析',
      'Bloomberg 風格市場熱力圖',
      'API 擴充至 60+ 端點',
      'SWR 即時資料 + API 快取 + Gzip 壓縮',
    ],
  },
  {
    version: 'v2.5.0',
    date: '2026-03-26',
    tag: 'Feature' as const,
    changes: [
      '盤後總覽新增 AI 策略選股（獲利優先 / 短期動能 / 長期存股）',
      '股票類型篩選切換（僅個股 / 含 ETF / 全部）',
      '移除社群輿情頁面',
      'UI/UX 全面翻新：統一 KPI 卡片、響應式 CSS、sidebar 智能展開',
      '儀表板重命名為「持倉總覽」消除導航混淆',
    ],
  },
  {
    version: 'v2.0.0',
    date: '2026-03-26',
    tag: 'Major' as const,
    changes: [
      'FastAPI REST API Server（57 個新端點）',
      '功能斷點串接：選股→警報、回測→投資組合、交易日誌→持倉同步',
      'Telegram Bot 通知（取代已停用的 LINE Notify）',
      '警報自動觸發整合至 launchd 排程',
      'API 策略重構：消除 api_server.py 邏輯重複',
      '統一三份資料映射表為 DATA_REGISTRY',
      '/screener RSI 向量化計算（30 秒→0.1 秒）',
      '快取統一為 DataCache 單例 + st.cache_data.clear()',
    ],
  },
  {
    version: 'v1.5.0',
    date: '2026-03-26',
    tag: 'Feature' as const,
    changes: [
      '第一輪 PM/SA/RD/QA 團隊 Code Review',
      '修復 3 個 Critical 安全問題（Token 洩漏、SSL、API 認證）',
      '修復布林通道返回值順序 Bug',
      '修復回測引擎資金計算缺陷',
      '修復 HTTP Client 重試靜默返回 None',
      '修復 cache_warmer 競態條件',
      '測試覆蓋率 15/41 → 41/41（100%）',
    ],
  },
  {
    version: 'v1.2.0',
    date: '2026-03-26',
    tag: 'Feature' as const,
    changes: [
      '第二輪 Review：修復 pandas 頻率相容性（M→ME）',
      '修復回測最後持倉永遠為空的問題',
      'Telegram 設定 UI 與通知引擎橋接',
      'DataCache Lock 改為 RLock 防止死鎖',
      'GrowthStrategy preset 補齊 use_consecutive',
      '移除全專案 47 處 sys.path.insert',
      '新增 pyproject.toml 支援 pip install -e .',
    ],
  },
  {
    version: 'v1.0.0',
    date: '2025-12-01',
    tag: 'Major' as const,
    changes: [
      '初始版本：Streamlit 台股監控系統',
      '25 個功能頁面（儀表板、選股、回測、技術分析等）',
      '核心引擎：策略篩選、回測引擎、風險分析',
      '資料來源：FinLab API + pickle 本地快取',
      '通知系統：LINE Notify / Email',
      'macOS launchd 排程自動更新',
      'Railway.app 雲端部署',
    ],
  },
  {
    version: 'v0.5.0',
    date: '2025-08-01',
    tag: 'Feature' as const,
    changes: [
      'AI 智慧選股（多因子量化評分）',
      '社群輿情分析（PTT Stock 版爬蟲）',
      '預測驗證系統',
      '每日晨報自動生成',
    ],
  },
  {
    version: 'v0.1.0',
    date: '2025-05-01',
    tag: null,
    changes: [
      '專案啟動',
      '基礎架構：Streamlit + pandas + FinLab API',
      '個股分析、技術指標計算',
    ],
  },
]
