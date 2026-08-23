import NextAuth from 'next-auth'
import Google from 'next-auth/providers/google'
import { canAccessPath } from '@/lib/auth/access'

export const { handlers, auth, signIn, signOut } = NextAuth({
  providers: [Google],
  session: { strategy: 'jwt' },
  pages: { signIn: '/login' },
  callbacks: {
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
      return canAccessPath(
        request.nextUrl.pathname,
        Boolean(session?.user?.id)
      )
    },
  },
})
