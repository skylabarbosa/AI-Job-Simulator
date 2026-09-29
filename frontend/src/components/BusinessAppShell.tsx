import { BarChart3, BookOpen, FolderKanban, LayoutDashboard, LogOut, Plus, UserRound } from 'lucide-react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import type { ReactNode } from 'react'

import { useAuth } from '../auth/useAuth'
import { Button } from './ui/button'

const businessNavItems = [
  { label: 'Projects', to: '/business/projects', icon: FolderKanban, exact: true },
  { label: 'New Project', to: '/business/projects/new', icon: Plus, exact: true },
]

export function BusinessAppShell({ children }: { children: ReactNode }) {
  const { profile, signOut } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const projectId = location.pathname.match(/^\/business\/projects\/([^/]+)/)?.[1]
  const isNewProject = location.pathname === '/business/projects/new'
  const mobileContext = isNewProject ? 'New project' : projectId ? 'Project workspace' : 'Projects'
  const displayName = profile?.display_name ?? 'Business user'
  const initials = (profile?.display_name ?? 'BU').slice(0, 2).toUpperCase()

  const handleSignOut = async () => {
    await signOut()
    navigate('/login', { replace: true })
  }

  return (
    <div className="business-app-shell">
      <a className="ui-skip-link" href="#main-content">Skip to content</a>

      {/* ── Sidebar ── */}
      <aside className="business-sidebar" aria-label="Business navigation">
        {/* Brand */}
        <Link className="business-brand" to="/business/projects" aria-label="SkillUp Business projects">
          <span className="business-brand-plate">
            <img src="/assets/brand/skillup-logo.png" alt="SkillUp" />
          </span>
          <span className="business-brand-badge">Business</span>
        </Link>

        {/* Primary nav */}
        <nav className="business-nav" aria-label="Business workspace">
          <div className="business-nav-section">
            <p className="business-nav-label">Workspace</p>
            {businessNavItems.map(({ label, to, icon: Icon, exact }) => {
              const isActive = exact ? location.pathname === to : location.pathname.startsWith(to)
              return (
                <Link
                  key={to}
                  className={`business-nav-link${isActive ? ' business-nav-link-active' : ''}`}
                  to={to}
                  aria-current={isActive ? 'page' : undefined}
                >
                  <Icon size={16} aria-hidden="true" />
                  <span>{label}</span>
                </Link>
              )
            })}
          </div>

          {/* Contextual project nav */}
          {projectId && !isNewProject && (
            <div className="business-nav-section business-project-context">
              <p className="business-nav-label">Current project</p>
              <Link
                className={`business-nav-link${location.pathname === `/business/projects/${projectId}` ? ' business-nav-link-active' : ''}`}
                to={`/business/projects/${projectId}`}
                aria-current="page"
              >
                <LayoutDashboard size={16} aria-hidden="true" />
                <span>Overview</span>
              </Link>
              <Link
                className="business-nav-link"
                to={`/business/projects/${projectId}#datasets`}
              >
                <BookOpen size={16} aria-hidden="true" />
                <span>Datasets</span>
              </Link>
              <Link
                className="business-nav-link"
                to={`/business/projects/${projectId}#blueprint`}
              >
                <BarChart3 size={16} aria-hidden="true" />
                <span>Blueprint</span>
              </Link>
            </div>
          )}
        </nav>

        {/* Footer */}
        <div className="business-sidebar-footer">
          <div className="business-nav-section">
            <p className="business-nav-label">Account</p>
            <div className="business-profile">
              <span className="business-avatar" aria-hidden="true">{initials}</span>
              <span>
                <strong>{displayName}</strong>
                <small>BUSINESS</small>
              </span>
            </div>
            <Button className="business-signout business-nav-link" variant="ghost" size="sm" onClick={handleSignOut}>
              <LogOut size={16} aria-hidden="true" />
              <span>Sign out</span>
            </Button>
          </div>
        </div>
      </aside>

      {/* ── Mobile header ── */}
      <header className="business-mobile-header">
        <Link className="business-brand" to="/business/projects" aria-label="SkillUp Business projects">
          <span className="business-brand-plate">
            <img src="/assets/brand/skillup-logo.png" alt="SkillUp" />
          </span>
        </Link>
        <span className="business-mobile-context" aria-current="page">{mobileContext}</span>
        <div className="business-mobile-user">
          <UserRound size={16} aria-hidden="true" />
          {displayName}
        </div>
      </header>

      <div className="business-main" id="main-content" tabIndex={-1}>{children}</div>
    </div>
  )
}
