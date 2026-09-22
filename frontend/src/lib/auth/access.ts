export function canAccessPath(pathname: string, authenticated: boolean): boolean {
  // API handlers enforce sessions themselves so unauthenticated callers receive
  // a machine-readable 401 instead of an HTML redirect to the login page.
  if (pathname === '/login' || pathname.startsWith('/api/')) {
    return true
  }
  return authenticated
}
