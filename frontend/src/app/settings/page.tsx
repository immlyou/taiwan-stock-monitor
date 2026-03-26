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
      </div>
    </div>
  )
}
