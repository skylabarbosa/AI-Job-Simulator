import { ArrowRight, CheckCircle2, CircleCheck, FolderKanban, Layers3, Search } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { ProjectIllustration, getProjectIllustrationSource } from '../components/ProjectIllustration'
import { Button, ButtonLink } from '../components/ui/button'
import { getLearnerProgress } from '../services/api/learner'
import { listAvailableProjects, type LearnerProjectWithStatus, withLearnerProgress } from '../services/api/projects'

export function LearnerProjectsPage() {
  const [projects, setProjects] = useState<LearnerProjectWithStatus[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [retryCount, setRetryCount] = useState(0)
  const [activeFilter, setActiveFilter] = useState<'all' | 'in_progress' | 'completed'>('all')
  const [searchQuery, setSearchQuery] = useState('')

  useEffect(() => {
    void Promise.all([listAvailableProjects(), getLearnerProgress()])
      .then(([availableProjects, progress]) => setProjects(withLearnerProgress(availableProjects, progress)))
      .catch((requestError) => {
        console.error('Unable to load learner projects.', requestError)
        setError('We could not load projects right now.')
      })
      .finally(() => setLoading(false))
  }, [retryCount])

  const visibleProjects = useMemo(() => {
    const query = searchQuery.trim().toLowerCase()
    return projects.filter((project) => {
      const matchesFilter = activeFilter === 'all' || project.learner_status === activeFilter
      const matchesSearch = !query || [project.name, project.project_summary, ...project.work_areas.map((area) => area.name)]
        .some((value) => value.toLowerCase().includes(query))
      return matchesFilter && matchesSearch
    })
  }, [activeFilter, projects, searchQuery])

  return (
    <main className="learner-dashboard">
      <div className="learner-decor learner-decor-one" aria-hidden="true" />
      <div className="learner-decor learner-decor-two" aria-hidden="true" />
      <div className="learner-dashboard-inner">
        <section className="learner-welcome learner-projects-intro" aria-labelledby="learner-projects-title">
          <div>
            <div className="learner-eyebrow">Hands-on learning</div>
            <h1 id="learner-projects-title">Projects</h1>
            <p>Explore real workplace projects and build practical skills through hands-on work.</p>
          </div>
          <div className="learner-welcome-aside">
            {!loading && !error && <span className="learner-project-count"><Layers3 size={16} /> {projects.length} available</span>}
            <label className="learner-project-search">
              <Search size={17} aria-hidden="true" />
              <span className="sr-only">Search projects</span>
              <input value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} placeholder="Search projects..." type="search" />
            </label>
          </div>
        </section>

        {error && (
          <div className="learner-alert" role="alert">
            <p>{error}</p>
            <Button variant="outline" onClick={() => { setLoading(true); setError(null); setRetryCount((count) => count + 1) }}>Retry</Button>
          </div>
        )}
        {loading && (
          <div className="learner-loading" aria-live="polite" aria-label="Loading projects">
            <p>Finding available projects...</p>
            <div className="learner-discover-grid" aria-hidden="true">
              {Array.from({ length: 3 }, (_, index) => <div className="learner-skeleton learner-skeleton-discover" key={index} />)}
            </div>
          </div>
        )}
        {!loading && !error && (
          <section className="learner-section learner-project-library" aria-labelledby="available-projects-title">
            <div className="learner-project-library-bar">
              <div className="learner-project-tabs" role="tablist" aria-label="Filter projects by progress">
                {[
                  ['all', 'All projects'],
                  ['in_progress', 'In progress'],
                  ['completed', 'Completed'],
                ].map(([value, label]) => (
                  <button
                    className={activeFilter === value ? 'learner-project-tab learner-project-tab-active' : 'learner-project-tab'}
                    key={value}
                    onClick={() => setActiveFilter(value as typeof activeFilter)}
                    role="tab"
                    aria-selected={activeFilter === value}
                    type="button"
                  >
                    {label}
                  </button>
                ))}
              </div>
              <span className="learner-muted" id="available-projects-title">Choose a project to begin or pick up where you left off</span>
            </div>
            {visibleProjects.length ? (
              <div className="learner-discover-grid">
                {visibleProjects.map((project) => (
                  <article className={`learner-discover-card learner-card-with-illustration learner-discover-card-${project.learner_status.replace('_', '-')}`} key={project.id}>
                    <div className="learner-discover-card-body">
                      <div className="learner-discover-card-top">
                        <span className={`learner-mini-badge learner-status-${project.learner_status.replace('_', '-')}`}>
                          {project.learner_status === 'completed' ? <CircleCheck size={14} aria-hidden="true" /> : <FolderKanban size={14} aria-hidden="true" />} {
                          project.learner_status === 'completed'
                            ? 'Completed'
                            : project.learner_status === 'in_progress'
                              ? 'In Progress'
                              : 'Not Started'
                        }</span>
                        <span className="learner-mini-meta">{project.work_areas.length} {project.work_areas.length === 1 ? 'work area' : 'work areas'}</span>
                      </div>
                      <h3>{project.name}</h3>
                      <p>{project.project_summary}</p>
                      <div className="learner-discover-progress">
                        <div className="learner-progress-label">
                          <span>{project.total_tasks > 0 ? `${project.completed_tasks} of ${project.total_tasks} tasks` : 'Ready when you are'}</span>
                          {project.total_tasks > 0 && <strong>{project.progress}%</strong>}
                        </div>
                        {project.total_tasks > 0 && (
                          <div className="learner-progress-track" role="progressbar" aria-label={`${project.name} progress`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={project.progress}>
                            <span style={{ width: `${Math.min(100, Math.max(0, project.progress))}%` }} />
                          </div>
                        )}
                      </div>
                      <div className="learner-project-snapshot" aria-label="Project snapshot">
                        <span><strong>{project.total_tasks}</strong> tasks</span>
                        <span><strong>{project.completed_tasks}</strong> completed</span>
                      </div>
                      <div className="learner-project-tags">
                        {project.work_areas.slice(0, 3).map((area) => <span key={`${project.id}-${area.name}`}>{area.name}</span>)}
                      </div>
                      <ButtonLink className="learner-inline-action" variant={project.learner_status === 'in_progress' ? 'default' : 'outline'} to={`/learner/projects/${project.id}`}>
                        {project.learner_status === 'in_progress' ? 'Continue project' : project.learner_status === 'completed' ? 'Review project' : 'Explore project'} <ArrowRight size={16} />
                      </ButtonLink>
                    </div>
                    <ProjectIllustration
                      projectName={project.name}
                      src={getProjectIllustrationSource(project.name)}
                      alt={`${project.name} project illustration`}
                      className="project-illustration-card"
                    />
                  </article>
                ))}
              </div>
            ) : (
              <div className="learner-empty-state">
                <span className="learner-empty-icon"><CheckCircle2 size={20} aria-hidden="true" /></span>
                <p>{searchQuery ? `No projects match “${searchQuery}”.` : 'No projects match this filter just yet.'}</p>
              </div>
            )}
          </section>
        )}
      </div>
    </main>
  )
}
