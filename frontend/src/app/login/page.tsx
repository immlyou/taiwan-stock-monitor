import { redirect } from 'next/navigation'

import { auth, signIn } from '@/auth'

export default async function LoginPage() {
  const session = await auth()
  if (session?.user?.id) redirect('/')

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
        <form action={signInWithGoogle}>
          <button
            type="submit"
            className="w-full h-11 rounded-md font-medium transition-opacity hover:opacity-90"
            style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}
          >
            使用 Google 登入
          </button>
        </form>
      </section>
    </main>
  )
}
