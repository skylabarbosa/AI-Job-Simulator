import { Navigate, useNavigate } from 'react-router-dom'

import { LearnerAppShell } from '../components/LearnerAppShell'
import { Button } from '../components/ui/button'
import { useAuth } from '../auth/useAuth'
import { LearnerDashboardPage } from './LearnerDashboardPage'

export function AuthenticatedPage() {
  const { profile, signOut } = useAuth()
  const navigate = useNavigate()

  const handleSignOut = async () => {
    await signOut()
    navigate('/login', { replace: true })
  }

  if (profile?.role === 'learner') {
    return (
      <LearnerAppShell>
        <LearnerDashboardPage />
      </LearnerAppShell>
    )
  }

  if (profile?.role === 'business' || profile?.role === 'admin') {
    return <Navigate to="/business/projects" replace />
  }

  return (
    <main className="workspace-shell">
      <section className="workspace-panel" aria-labelledby="workspace-title">
        <div>
          <div className="auth-eyebrow">Authenticated workspace</div>
          <h1 id="workspace-title">Good to see you, {profile?.display_name ?? 'there'}.</h1>
          <p className="auth-lede">Your {profile?.role} access is active. Simulation tools will appear here in a later phase.</p>
        </div>
        <Button variant="outline" onClick={handleSignOut}>Sign out</Button>
      </section>
    </main>
  )
}
