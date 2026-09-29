import { getSupabaseClient } from '../supabase.ts'

const configuredApiBaseUrl = import.meta.env?.VITE_API_BASE_URL
if (import.meta.env?.PROD && !configuredApiBaseUrl) {
  throw new Error('VITE_API_BASE_URL is required for the production frontend.')
}

const apiBaseUrl = configuredApiBaseUrl || 'http://localhost:8000/api'
const isDev = Boolean(typeof import.meta !== 'undefined' && import.meta.env?.DEV)

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

async function requestApi<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers)
  if (init?.body && !(init.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }

  try {
    const { data } = await getSupabaseClient().auth.getSession()
    if (data.session) headers.set('Authorization', `Bearer ${data.session.access_token}`)
  } catch {
    headers.delete('Authorization')
  }

  let response: Response
  try {
    response = await fetch(`${apiBaseUrl}${path}`, {
      ...init,
      headers,
    })
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Network request failed'
    if (isDev) {
      console.error(`[API Network Error] ${init?.method ?? 'GET'} ${apiBaseUrl}${path}:`, message)
    }
    throw new ApiError(message, { isNetworkError: true })
  }

  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null
    const detail = body?.detail
    const message = detail ?? `API request failed with status ${response.status}`
    if (isDev) {
      console.error(`[API Error ${response.status}] ${init?.method ?? 'GET'} ${apiBaseUrl}${path}:`, detail ?? message)
    }
    throw new ApiError(message, { status: response.status, detail })
  }

  return response.json() as Promise<T>
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