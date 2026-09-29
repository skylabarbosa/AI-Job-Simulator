import { useEffect, useRef, useState, type ReactNode } from 'react'
import type { Session } from '@supabase/supabase-js'

import { getSupabaseClient } from '../services/supabase'
import { setCachedSession } from '../services/authSession.ts'
import { AuthContext, type AppRole, type UserProfile } from './context'
import { authenticateAndLoadProfile, resolveAuthenticatedProfile, signOutAndClear } from './profileResolution'

function authErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message
  }
  return 'Authentication request failed. Please try again.'
}

async function loadProfile(userId: string): Promise<UserProfile> {
  return resolveAuthenticatedProfile(userId, async (id) => {
    const { data, error } = await getSupabaseClient()
      .from('users')
      .select('id, email, display_name, role')
      .eq('id', id)
      .maybeSingle()

    return { data: data as UserProfile | null, error }
  })
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [loading, setLoading] = useState(true)
  const [session, setSession] = useState<Session | null>(null)
  const [profile, setProfile] = useState<UserProfile | null>(null)
  const [error, setError] = useState<string | null>(null)
  const profileRequestId = useRef(0)

  useEffect(() => {
    let mounted = true
    let authEventReceived = false
    let supabase: ReturnType<typeof getSupabaseClient>

    try {
      supabase = getSupabaseClient()
    } catch (clientError) {
      queueMicrotask(() => {
        if (mounted) {
          setError(authErrorMessage(clientError))
          setLoading(false)
        }
      })
      return () => {
        mounted = false
      }
    }

    const applySession = async (nextSession: Session | null) => {
      const requestId = ++profileRequestId.current
      setLoading(Boolean(nextSession))
      setCachedSession(nextSession)
      setSession(nextSession)
      setProfile(null)
      setError(null)

      if (!nextSession) {
        setLoading(false)
        return
      }

      try {
        const nextProfile = await loadProfile(nextSession.user.id)
        if (mounted && requestId === profileRequestId.current) setProfile(nextProfile)
      } catch (profileError) {
        if (mounted && requestId === profileRequestId.current) setError(authErrorMessage(profileError))
      } finally {
        if (mounted && requestId === profileRequestId.current) setLoading(false)
      }
    }

    const restoreSession = async () => {
      try {
        const { data, error: sessionError } = await supabase.auth.getSession()
        if (sessionError) throw sessionError
        if (!mounted || authEventReceived) return
        await applySession(data.session)
      } catch (restoreError) {
        if (mounted && !authEventReceived) {
          setError(authErrorMessage(restoreError))
          setLoading(false)
        }
      }
    }

    void restoreSession()

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      authEventReceived = true
      setCachedSession(nextSession)
      queueMicrotask(() => {
        if (!mounted) return
        void applySession(nextSession)
      })
    })

    return () => {
      mounted = false
      profileRequestId.current += 1
      subscription.unsubscribe()
    }
  }, [])

  const signIn = async (email: string, password: string) => {
    const requestId = ++profileRequestId.current
    setLoading(true)
    setProfile(null)
    setError(null)

    try {
      const nextProfile = await authenticateAndLoadProfile(
        () => getSupabaseClient().auth.signInWithPassword({ email, password }),
        (_user, nextSession) => {
          if (requestId === profileRequestId.current) {
            setCachedSession(nextSession)
            setSession(nextSession)
          }
        },
        loadProfile,
      )
      if (requestId === profileRequestId.current) {
        setProfile(nextProfile)
        setLoading(false)
      }
      return nextProfile
    } catch (signInError) {
      if (requestId === profileRequestId.current) {
        setError(authErrorMessage(signInError))
        setLoading(false)
      }
      throw signInError
    }
  }

  const signUp = async (
    email: string,
    password: string,
    displayName: string,
    role: Exclude<AppRole, 'admin'>,
  ) => {
    setError(null)
    setLoading(true)
    try {
      const { data, error: signUpError } = await getSupabaseClient().auth.signUp({
        email,
        password,
        options: {
          data: { display_name: displayName, role },
        },
      })
      if (signUpError) throw signUpError

      if (data.session && data.user) {
        const requestId = ++profileRequestId.current
        setCachedSession(data.session)
        setSession(data.session)
        const nextProfile = await loadProfile(data.user.id)
        if (requestId === profileRequestId.current) setProfile(nextProfile)
        return false
      }

      setLoading(false)
      return true
    } catch (signUpError) {
      setError(authErrorMessage(signUpError))
      setLoading(false)
      throw signUpError
    }
  }

  const signOut = async () => {
    setError(null)
    await signOutAndClear(
      () => getSupabaseClient().auth.signOut(),
      () => {
        profileRequestId.current += 1
        setCachedSession(null)
        setSession(null)
        setProfile(null)
        setLoading(false)
      },
    )
  }

  return (
    <AuthContext.Provider
      value={{
        loading,
        user: session?.user ?? null,
        session,
        profile,
        error,
        signIn,
        signUp,
        signOut,
        clearError: () => setError(null),
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

