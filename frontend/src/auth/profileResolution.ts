import type { AppRole, UserProfile } from './context'

type ProfileLookupResult = {
  data: UserProfile | null
  error: unknown | null
}

export const missingProfileMessage =
  'Your account is authenticated, but its SkillUp profile has not been provisioned. Contact an administrator.'

export async function resolveAuthenticatedProfile(
  userId: string,
  lookupById: (id: string) => Promise<ProfileLookupResult>,
): Promise<UserProfile> {
  let result: ProfileLookupResult
  try {
    result = await lookupById(userId)
  } catch {
    throw new Error('Unable to load your SkillUp profile. Please try again.')
  }

  if (result.error) {
    throw new Error('Unable to load your SkillUp profile. Please try again.')
  }
  if (!result.data) {
    throw new Error(missingProfileMessage)
  }
  if (result.data.id !== userId) {
    throw new Error('The SkillUp profile does not match your authenticated account. Contact an administrator.')
  }
  if (!['learner', 'business', 'admin'].includes(result.data.role)) {
    throw new Error('Your SkillUp profile has an invalid role. Contact an administrator.')
  }

  return result.data
}

type PasswordAuthResult<TUser, TSession> = {
  data: { user: TUser | null; session: TSession | null }
  error: unknown | null
}

export async function authenticateAndLoadProfile<TUser extends { id: string }, TSession>(
  authenticate: () => Promise<PasswordAuthResult<TUser, TSession>>,
  onAuthenticated: (user: TUser, session: TSession | null) => void,
  loadProfile: (userId: string) => Promise<UserProfile>,
): Promise<UserProfile> {
  const { data, error } = await authenticate()
  if (error) throw error
  if (!data.user) {
    throw new Error('Supabase authentication completed without an authenticated user.')
  }

  onAuthenticated(data.user, data.session)
  return loadProfile(data.user.id)
}

export function loginRoleMismatchMessage(
  selectedRole: Exclude<AppRole, 'admin'>,
  actualRole: AppRole,
): string | null {
  if (actualRole === 'admin' || selectedRole === actualRole) return null

  const actualLabel = actualRole === 'business' ? 'Business' : 'Learner'
  const selectedLabel = selectedRole === 'business' ? 'Business' : 'Learner'
  return `This account is registered as a ${actualLabel} account. Please select ${selectedLabel} to continue.`
}

export function canAccessRole(actualRole: AppRole, allowedRoles: AppRole[]): boolean {
  return allowedRoles.includes(actualRole)
}

export async function signOutAndClear<TError>(
  signOut: () => Promise<{ error: TError | null }>,
  clearState: () => void,
): Promise<void> {
  const { error } = await signOut()
  if (error) throw error
  clearState()
}