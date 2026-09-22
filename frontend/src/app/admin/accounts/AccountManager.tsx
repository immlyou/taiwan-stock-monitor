'use client'

import { useState, type FormEvent } from 'react'
import useSWR from 'swr'
import { fetchAPI, ApiError } from '@/lib/api/client'
import { ROLE_LABELS, type Account, type AccountList, type AccountRole } from '@/lib/auth/accounts'

const control = 'rounded-md border border-border bg-background px-3 py-2 text-sm disabled:opacity-50'
function date(value: string | null) {
  return value ? new Date(value).toLocaleString('zh-TW', { timeZone: 'Asia/Taipei' }) : '尚無紀錄'
}
function message(error: unknown) {
  if (error instanceof ApiError) {
    try {
      const body = JSON.parse(error.message)
      if (typeof body.detail === 'string') return body.detail
    } catch { /* use status-specific fallback */ }
    if (error.status === 403) return '權限已變更或帳號已停用，請聯絡管理員。'
  }
  return '帳號服務暫時無法使用，請稍後重試。'
}

function RoleSelect({ value, onChange, label, disabled }: {
  value: AccountRole; onChange: (role: AccountRole) => void; label: string; disabled?: boolean
}) {
  return <select className={control} aria-label={label} value={value} disabled={disabled}
    onChange={(event) => onChange(event.target.value as AccountRole)}>
    {Object.entries(ROLE_LABELS).map(([role, title]) => <option key={role} value={role}>{title}</option>)}
  </select>
}

function AccountRow({ account, self, busy, save }: {
  account: Account; self: boolean; busy: boolean
  save: (account: Account, role: AccountRole, enabled: boolean) => Promise<void>
}) {
  const [role, setRole] = useState(account.role)
  const [enabled, setEnabled] = useState(account.enabled)
  const changed = role !== account.role || enabled !== account.enabled
  return <tr className="border-t border-border">
    <td className="p-3"><div className="font-medium">{account.email}{self && '（你）'}</div>
      <div className="text-xs text-muted-foreground">{account.name || '尚未完成 Google 登入'}</div></td>
    <td className="p-3"><RoleSelect label={`${account.email} 權限`} value={role} onChange={setRole} disabled={self || busy} /></td>
    <td className="p-3"><label className="flex items-center gap-2">
      <input type="checkbox" aria-label={`${account.email} 啟用`} checked={enabled}
        disabled={self || busy} onChange={(event) => setEnabled(event.target.checked)} />
      {enabled ? (account.user_id ? '已啟用' : '已邀請，待登入') : '已停用'}
    </label></td>
    <td className="p-3 text-sm whitespace-nowrap">{date(account.last_login_at)}</td>
    <td className="p-3"><button className={control} disabled={self || busy || !changed}
      onClick={() => {
        if (window.confirm(`確認將 ${account.email} 設為「${ROLE_LABELS[role]}／${enabled ? '啟用' : '停用'}」？既有登入的下一次 API 請求立即套用。`)) {
          void save(account, role, enabled)
        }
      }}>儲存</button></td>
  </tr>
}

export function AccountManager({ currentId }: { currentId: string }) {
  const { data, error, isLoading, mutate } = useSWR<AccountList>('/admin/accounts',
    (path: string) => fetchAPI<AccountList>(path),
    { revalidateOnFocus: true, refreshInterval: 30000, shouldRetryOnError: false })
  const [email, setEmail] = useState('')
  const [role, setRole] = useState<AccountRole>('member')
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState('')
  const [failure, setFailure] = useState('')

  async function perform(action: () => Promise<unknown>, success: string) {
    setBusy(true); setFailure(''); setNotice('')
    try {
      await action()
      setNotice(success)
      await mutate().catch(() => undefined)
    } catch (err) {
      setFailure(message(err))
      // A rejected stale edit or revoked administrator must reload live state.
      await mutate().catch(() => undefined)
    } finally { setBusy(false) }
  }

  async function invite(event: FormEvent) {
    event.preventDefault()
    await perform(async () => {
      await fetchAPI('/admin/accounts', { method: 'POST', body: JSON.stringify({ email, role }) })
      setEmail('')
    }, '已加入允許名單。請將網站連結提供給對方，系統不會寄送邀請信。')
  }

  async function save(account: Account, nextRole: AccountRole, enabled: boolean) {
    await perform(() => fetchAPI(`/admin/accounts/${account.id}`, {
      method: 'PATCH', body: JSON.stringify({ role: nextRole, enabled, revision: account.revision }),
    }), '權限已更新，下一次 API 請求即套用；不會刪除既有個人資料。')
  }

  return <div className="space-y-6 max-w-6xl mx-auto">
    <header><h1 className="text-2xl font-bold">帳號管理</h1>
      <p className="text-sm text-muted-foreground mt-2">Google 邀請名單、存取權限與登入紀錄。管理員不能查看其他人的投組或通知秘密。</p></header>
    <section className="rounded-lg border border-border p-4 text-sm space-y-2">
      <p>管理員：管理帳號、全域資料更新，以及自己的投研資料。</p>
      <p>一般使用者：查看行情、執行分析、編輯自己的投組／自選股／警報與設定。</p>
      <p>唯讀：查看行情與自己的資料；不能儲存變更、發送測試通知或執行需 POST 的分析。</p>
      <p className="text-muted-foreground">登入紀錄自此功能啟用後開始累積，舊登入不會回填。不能變更自己的角色或停用自己。</p>
    </section>
    {error ? <div role="alert" className="space-y-2"><p>{message(error)}</p>
      <button className={control} onClick={() => void mutate()}>重新載入</button></div>
      : isLoading || !data ? <p role="status">載入帳號中…</p> : <>
        <form onSubmit={invite} className="flex flex-wrap items-end gap-3 rounded-lg border border-border p-4">
          <label className="grid gap-1 text-sm">Google Email
            <input className={control} type="email" required maxLength={254} value={email}
              disabled={busy} onChange={(event) => setEmail(event.target.value)} placeholder="name@gmail.com" /></label>
          <RoleSelect label="邀請角色" value={role} onChange={setRole} disabled={busy} />
          <button className={control} type="submit" disabled={busy}>{busy ? '處理中…' : '加入帳號'}</button>
        </form>
        {failure && <p role="alert" className="text-destructive">{failure}</p>}
        {notice && <p role="status">{notice}</p>}
        <div className="overflow-x-auto rounded-lg border border-border"><table className="w-full text-left">
          <caption className="text-left p-3 font-medium">帳號清單（{data.accounts.length}）</caption>
          <thead><tr>{['Google 帳號', '權限', '狀態', '最近登入（台北）', '操作'].map((label) => <th className="p-3 text-sm" key={label}>{label}</th>)}</tr></thead>
          <tbody>{data.accounts.map((account) => <AccountRow key={`${account.id}:${account.revision}`} account={account}
            self={account.id === currentId} busy={busy} save={save} />)}</tbody>
        </table></div>
        <section><h2 className="font-semibold mb-2">最近操作紀錄</h2>
          <div className="overflow-x-auto"><table className="w-full text-sm text-left"><thead><tr>
            {['時間（台北）', '操作者', '操作', '目標帳號', '結果'].map((label) => <th className="p-2" key={label}>{label}</th>)}
          </tr></thead><tbody>{data.audit.map((entry, index) => <tr className="border-t border-border" key={`${entry.at}:${index}`}>
            <td className="p-2 whitespace-nowrap">{date(entry.at)}</td><td className="p-2">{entry.actor}</td>
            <td className="p-2">{{ bootstrap: '初始管理員', invite: '邀請', update: '權限變更', login: 'Google 登入' }[entry.action] || entry.action}</td>
            <td className="p-2">{entry.email}</td><td className="p-2">{ROLE_LABELS[entry.role]}／{entry.enabled ? '啟用' : '停用'}</td>
          </tr>)}</tbody></table></div>
          <p className="text-xs text-muted-foreground mt-2">保留最近 500 筆，顯示最近 100 筆；停用不會清除已下載的資料。</p>
        </section>
      </>}
  </div>
}
