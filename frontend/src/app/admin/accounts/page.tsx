import { auth } from '@/auth'
import { identityFromSession } from '@/lib/auth/identity'
import { getCurrentAccount, AccountAccessError } from '@/lib/auth/account-server'
import { redirect } from 'next/navigation'
import { AccountManager } from './AccountManager'

export default async function AccountsPage() {
  const identity = identityFromSession(await auth())
  if (!identity.authenticated) redirect('/login')
  let account
  try {
    account = await getCurrentAccount(identity)
  } catch (error) {
    return <section role="alert" className="space-y-3">
      <h1 className="text-xl font-semibold">帳號管理暫時無法開啟</h1>
      <p>{error instanceof AccountAccessError && error.status === 403
        ? '此帳號未獲授權或已停用，請聯絡管理員。'
        : '目前無法確認管理員權限，請稍後重新載入。'}</p>
      <a href="/admin/accounts" className="underline">重新載入</a>
    </section>
  }
  if (account.role !== 'admin') return <p role="alert">此頁面僅開放管理員使用。</p>
  return <AccountManager currentId={account.id} />
}
