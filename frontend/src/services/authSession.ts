import type { Session } from '@supabase/supabase-js'

// `undefined` means AuthProvider has not completed its initial restoration yet.
let cachedSession: Session | null | undefined

export function setCachedSession(session: Session | null): void {
  cachedSession = session
}

export function getCachedSession(): Session | null | undefined {
  return cachedSession
}
