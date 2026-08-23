export { auth as proxy } from '@/auth'

export const config = {
  matcher: [
    '/((?!_next/static|_next/image|favicon.ico|window.svg|globe.svg|next.svg|vercel.svg|file.svg).*)',
  ],
}
