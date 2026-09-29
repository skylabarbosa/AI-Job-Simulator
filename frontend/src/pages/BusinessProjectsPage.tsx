import { useEffect, useState } from 'react'
import { ArrowRight, Clock, FolderKanban, Plus, TrendingUp } from 'lucide-react'

import { Button, ButtonLink } from '../components/ui/button'
import { BusinessAppShell } from '../components/BusinessAppShell'
import { listProjects, type Project } from '../services/api/projects'

function StatusBadge({ status }: { status: Project['status'] }) {
  const map = {
    active: { label: 'Published', className: 'biz-status-active' },
    draft: { label: 'Draft', className: 'biz-status-draft' },
    archived: { label: 'Archived', className: 'biz-status-archived' },
  }
  const { label, className } = map[status] ?? { label: status, className: '' }
  return <span className={`biz-status-badge ${className}`}>{label}</span>
}

export function BusinessProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [retryCount, setRetryCount] = useState(0)

  useEffect(() => {
    void listProjects()
      .then(setProjects)
      .catch((requestError) => {
        console.error('Unable to load business projects.', requestError)
        setError('We could not load your projects right now.')
      })
      .finally(() => setLoading(false))
  }, [retryCount])

  const activeCount = projects.filter((p) => p.status === 'active').length
  const draftCount = projects.filter((p) => p.status === 'draft').length

  return (
    <BusinessAppShell>
      <main className="business-shell">
        <section className="business-content" aria-labelledby="projects-title">

          {/* ── Page header ── */}
          <div className="business-page-header">
            <div className="business-page-header-copy">
              <div className="biz-eyebrow">Business workspace</div>
              <h1 id="projects-title">Your Projects</h1>
              <p className="biz-sub">Shape workplace challenges into meaningful learning experiences for talented learners.</p>
            </div>
            <ButtonLink className="biz-new-btn" to="/business/projects/new">
              <Plus size={16} aria-hidden="true" />
              New Project
            </ButtonLink>
          </div>

          {/* ── Stats row ── */}
          {!loading && !error && projects.length > 0 && (
            <div className="biz-stats-row" aria-label="Project summary">
              <div className="biz-stat-chip">
                <FolderKanban size={15} aria-hidden="true" />
                <span><strong>{projects.length}</strong> Total</span>
              </div>
              <div className="biz-stat-chip biz-stat-chip-green">
                <TrendingUp size={15} aria-hidden="true" />
                <span><strong>{activeCount}</strong> Published</span>
              </div>
              <div className="biz-stat-chip biz-stat-chip-muted">
                <Clock size={15} aria-hidden="true" />
                <span><strong>{draftCount}</strong> Drafts</span>
              </div>
            </div>
          )}

          {/* ── Error ── */}
          {error && (
            <div className="biz-error-state" role="alert">
              <p>{error}</p>
              <Button
                variant="outline"
                onClick={() => { setLoading(true); setError(null); setRetryCount((c) => c + 1) }}
              >
                Retry
              </Button>
            </div>
          )}

          {/* ── Loading skeleton ── */}
          {loading && (
            <div className="biz-skeleton-list" aria-live="polite" aria-label="Loading projects">
              {Array.from({ length: 3 }, (_, i) => (
                <div className="biz-skeleton-card" key={i}>
                  <div className="biz-skeleton-line biz-skeleton-title" />
                  <div className="biz-skeleton-line biz-skeleton-body" />
                  <div className="biz-skeleton-line biz-skeleton-meta" />
                </div>
              ))}
            </div>
          )}

          {/* ── Empty state ── */}
          {!loading && !error && projects.length === 0 && (
            <div className="biz-empty-state">
              <span className="biz-empty-icon"><FolderKanban size={28} aria-hidden="true" /></span>
              <h2>No projects yet</h2>
              <p>Create your first project to start shaping a workplace learning experience for learners.</p>
              <ButtonLink className="biz-new-btn" to="/business/projects/new">
                <Plus size={16} aria-hidden="true" />
                Create your first project
              </ButtonLink>
            </div>
          )}

          {/* ── Project cards ── */}
          {!loading && !error && projects.length > 0 && (
            <div className="biz-project-grid">
              {projects.map((project) => (
                <article className="biz-project-card" key={project.id}>
                  <div className="biz-project-card-top">
                    <StatusBadge status={project.status} />
                    <time className="biz-project-date" dateTime={project.created_at}>
                      {new Date(project.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}
                    </time>
                  </div>
                  <h2 className="biz-project-title">{project.name}</h2>
                  {project.business_problem && (
                    <p className="biz-project-desc">{project.business_problem}</p>
                  )}
                  <div className="biz-project-card-footer">
                    <ButtonLink className="biz-open-btn" variant="outline" to={`/business/projects/${project.id}`}>
                      Open project <ArrowRight size={15} aria-hidden="true" />
                    </ButtonLink>
                  </div>
                </article>
              ))}

              {/* "Add new" card */}
              <ButtonLink className="biz-add-card" to="/business/projects/new" aria-label="Create a new project">
                <span className="biz-add-icon"><Plus size={22} /></span>
                <span>Create new project</span>
              </ButtonLink>
            </div>
          )}
        </section>
      </main>
    </BusinessAppShell>
  )
}
