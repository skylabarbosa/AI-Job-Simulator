import { useEffect, useState } from 'react'
import { ArrowRight, BookOpenCheck, CircleCheck, CircleDashed, Clock3 } from 'lucide-react'
import { ProjectIllustration, getProjectIllustrationSource } from '../components/ProjectIllustration'
import { ButtonLink } from '../components/ui/button'

import { getLearnerProgress, type LearnerProgressResponse } from '../services/api/learner'
import { Button } from '../components/ui/button'

export function LearnerProgressPage() {
  const [response, setResponse] = useState<LearnerProgressResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [retryCount, setRetryCount] = useState(0)

  useEffect(() => {
    let cancelled = false

    void getLearnerProgress()
      .then((data) => {
        if (!cancelled) setResponse(data)
      })
      .catch((requestError) => {
        console.error('Unable to load learner progress.', requestError)
        if (!cancelled) setError('We could not load your progress right now.')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [retryCount])

  return (
    <main className="learner-dashboard">
      <div className="learner-decor learner-decor-one" aria-hidden="true" />
      <div className="learner-decor learner-decor-two" aria-hidden="true" />
      <div className="learner-dashboard-inner">
        <section className="learner-welcome" aria-labelledby="learner-progress-title">
          <div>
            <div className="learner-eyebrow">Your learning journey</div>
            <h1 id="learner-progress-title">Your Progress</h1>
            <p>See what you have completed and pick up where you left off.</p>
          </div>
        </section>

        {error && (
          <div className="learner-alert" role="alert">
            <p>Your progress couldn’t be loaded.</p>
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                setLoading(true)
                setError(null)
                setResponse(null)
                setRetryCount((count) => count + 1)
              }}
            >
              Retry
            </Button>
          </div>
        )}
        {loading && (
          <div className="learner-loading" aria-live="polite" aria-label="Loading your progress">
            <p>Gathering your progress...</p>
            <div className="learner-metric-grid" aria-hidden="true">
              {Array.from({ length: 4 }, (_, index) => <div className="learner-skeleton learner-skeleton-metric" key={index} />)}
            </div>
            <div className="learner-skeleton learner-skeleton-project" aria-hidden="true" />
            <div className="learner-skeleton learner-skeleton-project" aria-hidden="true" />
          </div>
        )}

        {!loading && !error && response && (
          <>
            <section className="learner-section" aria-labelledby="progress-summary-heading">
              <div className="learner-section-heading">
                <div>
                  <div className="learner-eyebrow">Overview</div>
                  <h2 id="progress-summary-heading">At a glance</h2>
                </div>
              </div>
              <div className="learner-metric-grid">
                <article className="learner-metric-card">
                  <span className="learner-metric-label">Projects started</span>
                  <strong>{response.totals.projects_started}</strong>
                </article>
                <article className="learner-metric-card">
                  <span className="learner-metric-label">Completed projects</span>
                  <strong>{response.totals.completed_projects}</strong>
                </article>
                <article className="learner-metric-card">
                  <span className="learner-metric-label">Tasks completed</span>
                  <strong>{response.totals.completed_tasks}</strong>
                </article>
                <article className="learner-metric-card">
                  <span className="learner-metric-label">Average progress</span>
                  <strong>{response.totals.average_progress}%</strong>
                </article>
              </div>
            </section>

            <section className="learner-section" aria-labelledby="project-progress-heading">
              <div className="learner-section-heading">
                <div>
                  <div className="learner-eyebrow">Projects</div>
                  <h2 id="project-progress-heading">Your projects</h2>
                </div>
              </div>
              {response.projects.length ? (
                <div className="learner-project-list">
                  {response.projects.map((project) => {
                    const status = project.status?.trim() || (project.completed
                      ? 'Completed'
                      : project.completed_tasks > 0 ? 'In Progress' : 'Not Started')
                    const normalizedStatus = status.toLowerCase().replace(/[_-]+/g, ' ')
                    const isCompleted = project.completed || normalizedStatus === 'completed'
                    const isInProgress = normalizedStatus === 'in progress'
                    const StatusIcon = isCompleted ? CircleCheck : isInProgress ? Clock3 : CircleDashed
                    return (
                    <article className="learner-project-card learner-card-with-illustration" key={project.project_id}>
                      <ProjectIllustration
                        projectName={project.project_name ?? 'Project'}
                        src={getProjectIllustrationSource(project.project_name ?? 'Project')}
                        alt={`${project.project_name ?? 'Project'} project illustration`}
                        className="project-illustration-card"
                      />
                      <div className="learner-project-copy">
                        <div className="learner-project-top">
                          <span className={`learner-project-meta learner-status-${normalizedStatus.replace(/\s+/g, '-')}`}>
                            <StatusIcon size={14} aria-hidden="true" />
                            {status}
                          </span>
                          <span className="learner-project-activity">{project.completed_tasks} of {project.total_tasks} tasks</span>
                        </div>
                        <h3>{project.project_name ?? 'Project'}</h3>
                        <div className="learner-progress-label">
                          <span>Project progress</span>
                          <strong>{project.progress}%</strong>
                        </div>
                        <div className="learner-progress-track">
                          <span style={{ width: `${project.progress}%` }} />
                        </div>
                        <div className="learner-project-footer">
                          <ButtonLink variant="outline" to={`/learner/projects/${project.project_id}`}>
                            {isCompleted ? 'Review project' : isInProgress ? 'Continue project' : 'Explore project'} <ArrowRight size={16} aria-hidden="true" />
                          </ButtonLink>
                        </div>
                      </div>
                    </article>
                    )
                  })}
                </div>
              ) : (
                <div className="learner-empty-state">
                  <span className="learner-empty-icon"><BookOpenCheck size={20} aria-hidden="true" /></span>
                  <p>No progress to show yet. Explore a project and start your first task.</p>
                </div>
              )}
            </section>

            <section className="learner-section" aria-labelledby="recent-activity-heading">
              <div className="learner-section-heading">
                <div>
                  <div className="learner-eyebrow">Recent activity</div>
                  <h2 id="recent-activity-heading">What you have been working on</h2>
                </div>
              </div>
              {response.recent_activity.length > 0 ? (
                <ul className="learner-activity-list">
                  {response.recent_activity.slice(0, 5).map((activity, index) => (
                    <li key={`${activity.task_id ?? activity.project_id ?? 'activity'}-${activity.submitted_at ?? index}`}>
                      <span className="learner-activity-mark" aria-hidden="true"><BookOpenCheck size={16} /></span>
                      <span className="learner-activity-copy">
                        <strong>{activity.task_title ?? 'Task activity'}</strong>
                        <span>{activity.project_name ?? 'Project'}</span>
                      </span>
                      {activity.submitted_at && <time dateTime={activity.submitted_at}>{new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(new Date(activity.submitted_at))}</time>}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="learner-muted">Your recent work will appear here after you start a task.</p>
              )}
            </section>
          </>
        )}
      </div>
    </main>
  )
}
