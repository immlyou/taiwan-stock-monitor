import { redirect } from 'next/navigation'

import { auth, signIn, signOut } from '@/auth'
import { identityFromSession } from '@/lib/auth/identity'
import { getCurrentAccount } from '@/lib/auth/account-server'

export default async function LoginPage({ searchParams }: {
  searchParams: Promise<{ error?: string }>
}) {
  const { error } = await searchParams
  const session = await auth()
  const identity = identityFromSession(session)
  let active = false
  if (identity.authenticated) {
    try { await getCurrentAccount(identity); active = true } catch { /* show recovery/sign-out */ }
  }
  if (active && !error) redirect('/')

  async function signInWithGoogle() {
    'use server'
    await signIn('google', { redirectTo: '/' })
  }

  return (
    <main className="min-h-screen flex items-center justify-center p-6" style={{ background: 'var(--background)' }}>
      <section
        className="w-full max-w-md rounded-xl p-8 text-center"
        style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
      >
        <p className="text-sm mb-2" style={{ color: 'var(--primary)' }}>台股戰情中心</p>
        <h1 className="text-2xl font-bold mb-3" style={{ color: 'var(--foreground)' }}>
          登入你的投研工作台
        </h1>
        <p className="text-sm mb-8" style={{ color: 'var(--muted-foreground)' }}>
          投資組合、自選股、警報與設定會依 Google 帳號分開保存。
        </p>
        {(error || identity.authenticated) && <p role="alert" className="text-sm mb-4">
          {error === 'ServiceUnavailable' ? '帳號服務暫時無法使用，請稍後重試。'
            : '請使用已受邀且啟用的 Google 帳號；若無法登入，請聯絡管理員。'}
        </p>}
        <form action={signInWithGoogle}>
          <button
            type="submit"
            className="w-full h-11 rounded-md font-medium transition-opacity hover:opacity-90"
            style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}
          >
            使用 Google 登入
          </button>
        </form>
        {identity.authenticated && <form action={async () => {
          'use server'
          await signOut({ redirectTo: '/login' })
        }}><button className="mt-4 underline" type="submit">登出並切換帳號</button></form>}
      </section>
    </main>
  )
}
