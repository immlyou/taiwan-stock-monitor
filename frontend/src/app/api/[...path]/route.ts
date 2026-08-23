// 後端 API proxy：瀏覽器的 /api/* 請求由此轉發到 Railway 後端，
// 並在 server 端注入 Bearer token（STOCK_API_KEY 為 server-only 環境變數，
// 永遠不會進到 client bundle）。
//
// 取代原本 next.config.ts 的 rewrite——rewrite 無法附加 request header，
// 後端 auth 改為 fail-closed 後必須由這層帶上金鑰。
import type { NextRequest } from 'next/server'
import { auth } from '@/auth'
import { identityFromSession } from '@/lib/auth/identity'

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const API_KEY = process.env.STOCK_API_KEY
const DEFAULT_UPSTREAM_TIMEOUT_MS = 25_000
const AI_UPSTREAM_TIMEOUT_MS = 65_000
const ADVISOR_UPSTREAM_TIMEOUT_MS = 95_000
const REFRESH_UPSTREAM_TIMEOUT_MS = 110_000

// /refresh 全市場重新下載可能耗時，放寬到 120 秒
export const maxDuration = 120

async function proxy(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const identity = identityFromSession(
    await auth(),
    process.env.AUTH_ALLOWED_EMAIL
  )
  if (!identity.authenticated) {
    return Response.json(
      { error: 'authentication_required' },
      { status: 401 }
    )
  }

  const { path } = await params
  const url = `${BACKEND_URL}/${path.join('/')}${request.nextUrl.search}`
  const upstreamTimeoutMs = path[0] === 'refresh'
    ? REFRESH_UPSTREAM_TIMEOUT_MS
    : path[0] === 'advisor'
      ? ADVISOR_UPSTREAM_TIMEOUT_MS
      : path[0] === 'ai' || path[0] === 'scanner'
        ? AI_UPSTREAM_TIMEOUT_MS
        : DEFAULT_UPSTREAM_TIMEOUT_MS

  const headers = new Headers()
  const contentType = request.headers.get('content-type')
  if (contentType) headers.set('content-type', contentType)
  if (API_KEY) headers.set('authorization', `Bearer ${API_KEY}`)
  headers.set('x-user-id', identity.userId)

  const hasBody = request.method !== 'GET' && request.method !== 'HEAD'
  const body = hasBody ? await request.arrayBuffer() : undefined

  const upstreamController = new AbortController()
  let timedOut = false
  const abortUpstream = () => upstreamController.abort(request.signal.reason)
  if (request.signal.aborted) abortUpstream()
  request.signal.addEventListener('abort', abortUpstream, { once: true })
  const timeoutId = setTimeout(() => {
    timedOut = true
    upstreamController.abort(new DOMException('upstream timeout', 'TimeoutError'))
  }, upstreamTimeoutMs)

  let response: Response
  try {
    response = await fetch(url, {
      method: request.method,
      headers,
      body,
      cache: 'no-store',
      signal: upstreamController.signal,
    })
  } catch (error) {
    if (upstreamController.signal.aborted) {
      return Response.json(
        { error: timedOut ? 'upstream_timeout' : 'request_cancelled' },
        { status: timedOut ? 504 : 499 }
      )
    }
    throw error
  } finally {
    clearTimeout(timeoutId)
    request.signal.removeEventListener('abort', abortUpstream)
  }

  // fetch 已自動解壓縮，移除與原始編碼相關的 header 避免長度不符
  const responseHeaders = new Headers(response.headers)
  responseHeaders.delete('content-encoding')
  responseHeaders.delete('content-length')
  responseHeaders.delete('transfer-encoding')

  return new Response(response.body, {
    status: response.status,
    headers: responseHeaders,
  })
}

export {
  proxy as GET,
  proxy as POST,
  proxy as PUT,
  proxy as PATCH,
  proxy as DELETE,
}
