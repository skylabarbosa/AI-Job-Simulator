import { Navigate, Outlet, useLocation } from 'react-router-dom'

import { type AppRole } from '../auth/context'
import { useAuth } from '../auth/useAuth'
import { missingProfileMessage, canAccessRole } from '../auth/profileResolution'

export function ProtectedRoute({ roles }: { roles?: AppRole[] }) {
  const { loading, user, profile, error } = useAuth()
  const location = useLocation()

  if (loading) {
    return <main className="auth-state">Restoring your session...</main>
  }

  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }

  if (!profile) {
    return <main className="auth-state"><p className="auth-error" role="alert">{error ?? missingProfileMessage}</p></main>
  }

  if (roles && !canAccessRole(profile.role, roles)) {
    return <Navigate to="/unauthorized" replace />
  }

  return <Outlet />
}
