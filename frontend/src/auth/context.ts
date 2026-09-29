import { createContext } from 'react'
import type { Session, User } from '@supabase/supabase-js'

export type AppRole = 'learner' | 'business' | 'admin'

export interface UserProfile {
  id: string
  email: string | null
  display_name: string | null
  role: AppRole
}

export interface AuthContextValue {
  loading: boolean
  user: User | null
  session: Session | null
  profile: UserProfile | null
  error: string | null
  signIn: (email: string, password: string) => Promise<UserProfile>
  signUp: (email: string, password: string, displayName: string, role: Exclude<AppRole, 'admin'>) => Promise<boolean>
  signOut: () => Promise<void>
  clearError: () => void
}

export const AuthContext = createContext<AuthContextValue | undefined>(undefined)
