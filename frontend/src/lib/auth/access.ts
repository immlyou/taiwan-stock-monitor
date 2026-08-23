export function isAllowedGoogleAccount(
  email: string | null | undefined,
  configuredEmail: string | undefined
): boolean {
  if (!email || !configuredEmail) return false
  return configuredEmail.trim().toLowerCase() === email.trim().toLowerCase()
}

export function canAccessPath(pathname: string, authenticated: boolean): boolean {
  // API handlers enforce sessions themselves so unauthenticated callers receive
  // a machine-readable 401 instead of an HTML redirect to the login page.
  if (pathname === '/login' || pathname.startsWith('/api/')) {
    return true
  }
  return authenticated
}
