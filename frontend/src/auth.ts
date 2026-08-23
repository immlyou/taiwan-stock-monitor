import NextAuth from 'next-auth'
import Google from 'next-auth/providers/google'
import { canAccessPath, isAllowedGoogleAccount } from '@/lib/auth/access'
import { identityFromSession } from '@/lib/auth/identity'

export const { handlers, auth, signIn, signOut } = NextAuth({
  providers: [Google],
  session: { strategy: 'jwt' },
  pages: { signIn: '/login' },
  callbacks: {
    signIn({ user, account }) {
      return Boolean(
        account?.provider === 'google' &&
        isAllowedGoogleAccount(user.email, process.env.AUTH_ALLOWED_EMAIL)
      )
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
      const identity = identityFromSession(
        session,
        process.env.AUTH_ALLOWED_EMAIL
      )
      return canAccessPath(
        request.nextUrl.pathname,
        identity.authenticated
      )
    },
  },
})
