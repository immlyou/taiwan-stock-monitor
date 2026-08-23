import { isAllowedGoogleAccount } from './access'

export type AuthSessionLike = {
  user?: {
    id?: string | null
    email?: string | null
  } | null
} | null

export type ProxyIdentity =
  | { authenticated: false }
  | { authenticated: true; userId: string; email: string | null }

const SAFE_USER_ID = /^[A-Za-z0-9_-]{3,128}$/

export function identityFromSession(
  session: AuthSessionLike,
  configuredEmail?: string
): ProxyIdentity {
  const userId = session?.user?.id?.trim()
  if (
    !userId ||
    !SAFE_USER_ID.test(userId) ||
    !isAllowedGoogleAccount(session?.user?.email, configuredEmail)
  ) {
    return { authenticated: false }
  }

  return {
    authenticated: true,
    userId,
    email: session?.user?.email ?? null,
  }
}
