import { getSupabaseClient } from '../supabase.ts'
import { getCachedSession, setCachedSession } from '../authSession.ts'

const configuredApiBaseUrl = import.meta.env?.VITE_API_BASE_URL
if (import.meta.env?.PROD && !configuredApiBaseUrl) {
  throw new Error('VITE_API_BASE_URL is required for the production frontend.')
}

const apiBaseUrl = configuredApiBaseUrl || 'http://localhost:8000/api'
const isDev = Boolean(typeof import.meta !== 'undefined' && import.meta.env?.DEV)
const requestTimeoutMs = 30_000

export interface ApiErrorOptions {
  status?: number
  detail?: string
  isNetworkError?: boolean
}

export class ApiError extends Error {
  status?: number
  detail?: string
  isNetworkError?: boolean

  constructor(message: string, options?: ApiErrorOptions) {
    super(message)
    this.name = 'ApiError'
    this.status = options?.status
    this.detail = options?.detail
    this.isNetworkError = options?.isNetworkError
  }
}

async function getAccessToken(): Promise<string | null> {
  const session = getCachedSession()
  const isExpired = session?.expires_at !== undefined && session.expires_at <= Date.now() / 1000

  if (session !== undefined && !isExpired) {
    return session?.access_token ?? null
  }

  const { data, error } = await getSupabaseClient().auth.getSession()
  if (error) throw error

  setCachedSession(data.session)
  return data.session?.access_token ?? null
}

async function revalidateSession(): Promise<void> {
  try {
    const supabase = getSupabaseClient()
    const { error: userError } = await supabase.auth.getUser()
    if (userError) return

    const { data, error: sessionError } = await supabase.auth.getSession()
    if (!sessionError) setCachedSession(data.session)
  } catch {
    // The original API response remains authoritative; revalidation is best-effort.
  }
}

async function requestApi<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers)
  if (init?.body && !(init.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }

  try {
    const accessToken = await getAccessToken()
    if (!accessToken) {
      throw new ApiError('Authentication is required to make API requests.', { status: 401 })
    }
    headers.set('Authorization', `Bearer ${accessToken}`)
  } catch (error) {
    if (error instanceof ApiError) throw error
    throw new ApiError('Unable to restore the authenticated session.', { status: 401 })
  }

  const controller = new AbortController()
  const timeoutId = window.setTimeout(() => controller.abort(), requestTimeoutMs)
  try {
    const response = await fetch(`${apiBaseUrl}${path}`, {
      ...init,
      headers,
      signal: controller.signal,
    })

    if (!response.ok) {
      const body = (await response.json().catch(() => null)) as { detail?: string } | null
      const detail = body?.detail
      const message = detail ?? `API request failed with status ${response.status}`
      if (isDev) {
        console.error(`[API Error ${response.status}] ${init?.method ?? 'GET'} ${apiBaseUrl}${path}:`, detail ?? message)
      }
      if (response.status === 401) void revalidateSession()
      throw new ApiError(message, { status: response.status, detail })
    }

    return response.json() as Promise<T>
  } catch (error) {
    if (error instanceof ApiError) throw error
    const message = error instanceof DOMException && error.name === 'AbortError'
      ? `API request timed out after ${requestTimeoutMs / 1000} seconds`
      : error instanceof Error ? error.message : 'Network request failed'
    if (isDev) {
      console.error(`[API Network Error] ${init?.method ?? 'GET'} ${apiBaseUrl}${path}:`, message)
    }
    throw new ApiError(message, { isNetworkError: true })
  } finally {
    window.clearTimeout(timeoutId)
  }
}

export function getApi<T>(path: string): Promise<T> {
  return requestApi<T>(path)
}

export function postApi<T>(path: string, body?: unknown): Promise<T> {
  return requestApi<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) })
}

export function patchApi<T>(path: string, body: unknown): Promise<T> {
  return requestApi<T>(path, { method: 'PATCH', body: JSON.stringify(body) })
}

export function postFileApi<T>(path: string, file: File): Promise<T> {
  const body = new FormData()
  body.append('file', file)
  return requestApi<T>(path, { method: 'POST', body })
}

export function deleteApi(path: string): Promise<void> {
  return requestApi<void>(path, { method: 'DELETE' })
}
