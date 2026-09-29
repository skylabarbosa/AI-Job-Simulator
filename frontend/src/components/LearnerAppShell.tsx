import { BarChart3, Bell, CircleHelp, LayoutDashboard, LogOut, PanelsTopLeft, Sparkles, TrendingUp } from 'lucide-react'
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom'
import type { ReactNode } from 'react'

import { useAuth } from '../auth/useAuth'
import { Button } from './ui/button'

interface LearnerAppShellProps {
  children?: ReactNode
}

export const learnerNavItems = [
  { label: 'Dashboard', to: '/app', icon: LayoutDashboard },
  { label: 'Projects', to: '/learner/projects', icon: PanelsTopLeft },
  { label: 'My Progress', to: '/learner/progress', icon: BarChart3 },
  { label: 'Skills', to: '/learner/skills', icon: Sparkles },
]

export function LearnerAppShell({ children }: LearnerAppShellProps) {
  const { profile, signOut } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const isWorkspace = location.pathname.includes('/tasks/') && location.pathname.endsWith('/workspace')
  const displayName = profile?.display_name ?? 'Learner'
  const initials = displayName.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join('').toUpperCase() || 'LR'
  const activeNavLabel = isWorkspace
    ? 'Task workspace'
    : learnerNavItems.find(({ to }) => to === '/app'
      ? location.pathname === '/app' && !location.hash
      : location.pathname.startsWith(to))?.label ?? 'Learner space'

  const handleSignOut = async () => {
    await signOut()
    navigate('/login', { replace: true })
  }

  const renderNavItems = (className: string) => learnerNavItems.map(({ label, to, icon: Icon }) => {
    const isActive = to === '/app'
      ? location.pathname === '/app' && !location.hash
      : location.pathname.startsWith(to)
    return (
      <Link
        className={`${className}${isActive ? ' learner-nav-link-active' : ''}`}
        to={to}
        key={to}
        title={label}
        aria-current={isActive ? 'page' : undefined}
      >
        <span className="learner-nav-icon"><Icon size={17} aria-hidden="true" /></span>
        <span>{label}</span>
        {isActive && <span className="learner-nav-active-pill" aria-hidden="true" />}
      </Link>
    )
  })

  return (
    <div className="learner-app-shell">
      <a className="ui-skip-link" href="#main-content">Skip to content</a>

      {/* ── Sidebar ── */}
      <aside className="learner-sidebar" aria-label="Learner sidebar">
        {/* Brand */}
        <div className="learner-sidebar-head">
          <Link className="learner-brand" to="/app" aria-label="SkillUp dashboard">
            <span className="learner-brand-plate">
              <img src="/assets/brand/skillup-logo.png" alt="SkillUp" />
            </span>
          </Link>
          <button className="learner-notifications" type="button" aria-label="Notifications">
            <Bell size={16} />
          </button>
        </div>

        {/* Nav */}
        <nav className="learner-nav" aria-label="Learner navigation">
          <div className="learner-nav-section-label">Menu</div>
          {renderNavItems('learner-nav-link')}
        </nav>

        {/* Learning streak / mini widget */}
        <div className="learner-sidebar-streak" aria-label="Weekly activity">
          <div className="learner-streak-header">
            <TrendingUp size={14} aria-hidden="true" />
            <span>Your streak</span>
          </div>
          <div className="learner-streak-dots" aria-hidden="true">
            {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map((day, i) => (
              <div key={day} className="learner-streak-day">
                <span className={`learner-streak-dot${i < 5 ? ' learner-streak-dot-active' : ''}`} />
                <span>{day}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Footer */}
        <div className="learner-sidebar-footer">
          <a className="learner-sidebar-utility" href="mailto:support@skillup.example">
            <CircleHelp size={16} aria-hidden="true" />
            <span>Help &amp; Support</span>
          </a>
          <Button className="learner-signout learner-sidebar-utility" variant="ghost" size="sm" onClick={handleSignOut} aria-label="Sign out">
            <LogOut size={16} aria-hidden="true" />
            <span>Sign out</span>
          </Button>
          <div className="learner-profile" aria-label={`${displayName}, learner`}>
            <span className="learner-avatar" aria-hidden="true">{initials}</span>
            <span className="learner-profile-copy">
              <strong>{displayName}</strong>
              <small>LEARNER</small>
            </span>
          </div>
        </div>
      </aside>

      {/* ── Mobile header ── */}
      <header className="learner-mobile-header">
        <Link className="learner-brand" to="/app" aria-label="SkillUp dashboard">
          <span className="learner-brand-plate">
            <img src="/assets/brand/skillup-logo.png" alt="SkillUp" />
          </span>
        </Link>
        <span className="learner-mobile-context" aria-current="page">{activeNavLabel}</span>
        <div className="learner-profile" aria-label={`${displayName}, learner`}>
          <span className="learner-avatar" aria-hidden="true">{initials}</span>
        </div>
      </header>

      {/* ── Bottom nav (mobile) ── */}
      <nav
        className={`learner-bottom-nav${isWorkspace ? ' learner-bottom-nav-hidden' : ''}`}
        aria-label="Mobile learner navigation"
        aria-hidden={isWorkspace}
      >
        {renderNavItems('learner-bottom-nav-link')}
      </nav>

      {/* ── Main content ── */}
      <div id="main-content" tabIndex={-1}>
        {children ?? <Outlet />}
      </div>
    </div>
  )
}
