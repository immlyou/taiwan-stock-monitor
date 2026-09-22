export type AuthSessionLike = {
  user?: {
    id?: string | null
    email?: string | null
  } | null
} | null

export type ProxyIdentity =
  | { authenticated: false }
  | { authenticated: true; userId: string; email: string }

const SAFE_USER_ID = /^google_[A-Za-z0-9_-]{1,120}$/

export function identityFromSession(
  session: AuthSessionLike
): ProxyIdentity {
  const userId = session?.user?.id?.trim()
  if (
    !userId ||
    !SAFE_USER_ID.test(userId) ||
    !session?.user?.email?.trim()
  ) {
    return { authenticated: false }
  }

  return {
    authenticated: true,
    userId,
    email: session.user.email.trim().toLowerCase(),
  }
}
