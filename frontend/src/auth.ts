import NextAuth from 'next-auth'
import Google from 'next-auth/providers/google'
import { canAccessPath } from '@/lib/auth/access'
import { identityFromSession } from '@/lib/auth/identity'
import { accountRequest, AccountAccessError } from '@/lib/auth/account-server'

export const { handlers, auth, signIn, signOut } = NextAuth({
  providers: [Google],
  session: { strategy: 'jwt' },
  pages: { signIn: '/login', error: '/login' },
  callbacks: {
    async signIn({ user, account, profile }) {
      if (account?.provider !== 'google' || !account.providerAccountId ||
          profile?.email_verified !== true || !user.email ||
          profile.email?.toLowerCase() !== user.email.toLowerCase()) return false
      try {
        await accountRequest('/internal/accounts/google-login', {
          method: 'POST', body: JSON.stringify({
            user_id: `google_${account.providerAccountId}`, email: user.email,
            name: (user.name || '').slice(0, 120),
            bootstrap_email: process.env.AUTH_ALLOWED_EMAIL || '',
          }),
        })
        return true
      } catch (error) {
        return error instanceof AccountAccessError && error.status === 403
          ? false : '/login?error=ServiceUnavailable'
      }
    },
    jwt({ token, account }) {
      if (account?.provider === 'google' && account.providerAccountId) {
        token.userId = `google_${account.providerAccountId}`
      }
      return token
    },
    session({ session, token }) {
      if (session.user && typeof token.userId === 'string') {
        session.user.id = token.userId
      }
      return session
    },
    authorized({ auth: session, request }) {
      const identity = identityFromSession(session)
      return canAccessPath(
        request.nextUrl.pathname,
        identity.authenticated
      )
    },
  },
})
