import { ArrowRight, BarChart3, BookOpen, CheckCircle2, FolderKanban, Sparkles } from 'lucide-react'
import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

import { useAuth } from '../auth/useAuth'
import { ProjectIllustration, getProjectIllustrationSource } from '../components/ProjectIllustration'
import { ButtonLink } from '../components/ui/button'
import type { ProjectPerformance, SkillProgress } from '../services/api/performance'
import { getLearnerProgress, getLearnerSkills, type LearnerProgressResponse } from '../services/api/learner'
import { listAvailableProjects, type LearnerProject } from '../services/api/projects'

interface ProjectSnapshot {
  project: LearnerProject
  performance: ProjectPerformance | null
}

export function LearnerDashboardPage() {
  const { profile } = useAuth()
  const [projects, setProjects] = useState<ProjectSnapshot[]>([])
  const [progressResponse, setProgressResponse] = useState<LearnerProgressResponse | null>(null)
  const [skills, setSkills] = useState<SkillProgress[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    void Promise.all([listAvailableProjects(), getLearnerProgress(), getLearnerSkills()])
      .then(([availableProjects, learnerProgress, learnerSkills]) => {
        const progressByProject = new Map(learnerProgress.projects.map((item) => [item.project_id, item]))
        const snapshots = availableProjects.map((project) => ({
          project,
          performance: performanceFromProgress(project.id, progressByProject.get(project.id)),
        }))

        if (!cancelled) {
          setProjects(snapshots)
          setProgressResponse(learnerProgress)
          setSkills(learnerSkills.skills)
        }
      })
      .catch((requestError) => {
        if (!cancelled) {
          setError(requestError instanceof Error ? requestError.message : 'Unable to load your dashboard.')
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false)
        }
      })

    return () => {
      cancelled = true
    }
  }, [])

  const activeProjects = projects.filter(({ performance }) => performance && !performance.completed)
  const currentProject = projects.find(({ performance }) => performance && !performance.completed) ?? projects[0]
  const currentTask = currentProject?.performance?.tasks.find((task) => !task.completed) ?? currentProject?.performance?.tasks[0]
  const projectCards = projects.filter(({ project }) => project.id !== currentProject?.project.id)
  const completedTasks = progressResponse?.totals.completed_tasks ?? projects.reduce((total, item) => total + (item.performance?.completed_tasks ?? 0), 0)
  const totalTasks = progressResponse?.totals.total_tasks ?? projects.reduce((total, item) => total + (item.performance?.total_tasks ?? 0), 0)
  const averageProgressValue = progressResponse?.totals.average_progress ?? averageProgress(projects)

  return (
    <main className="learner-dashboard">
      <div className="learner-decor learner-decor-one" aria-hidden="true" />
      <div className="learner-decor learner-decor-two" aria-hidden="true" />
      <div className="learner-dashboard-inner">
        <section className="learner-hero" aria-labelledby="learner-dashboard-title">
          <div className="learner-hero-copy">
            <div className="learner-eyebrow">Learner dashboard</div>
            <h1 id="learner-dashboard-title">Good morning, {profile?.display_name ?? 'learner'}</h1>
            {currentProject ? (
              <>
                <p className="learner-hero-kicker">Continue where you left off</p>
                <h2>{currentProject.project.name}</h2>
                <p className="learner-hero-task">{currentTask?.title ?? currentProject.project.project_summary}</p>
                {currentProject.performance && <div className="learner-hero-progress" aria-label={`${currentProject.performance.progress}% complete`}><span style={{ width: `${Math.min(100, Math.max(0, currentProject.performance.progress))}%` }} /></div>}
                <ButtonLink className="learner-hero-action" to={currentTask ? `/learner/projects/${currentProject.project.id}/tasks/${currentTask.task_id}/workspace` : `/learner/projects/${currentProject.project.id}`}>
                  {currentProject.performance?.completed ? 'Review project' : 'Continue task'} <ArrowRight size={17} />
                </ButtonLink>
              </>
            ) : <p>Choose a project to start building practical skills.</p>}
          </div>
          <div className="learner-hero-mark" aria-hidden="true">
            {currentProject ? (
              <ProjectIllustration
                projectName={currentProject.project.name}
                src={getProjectIllustrationSource(currentProject.project.name)}
                alt=""
                className="learner-hero-illustration"
              />
            ) : <Sparkles size={30} />}
          </div>
        </section>

        {error && <p className="learner-alert" role="alert">{error}</p>}
        {loading && <p className="learner-loading learner-loading-dashboard" aria-live="polite">Loading your learning space...</p>}

        {!loading && !error && (
          <>
            <section className="learner-section" id="progress-summary" aria-labelledby="progress-title">
              <div className="learner-section-heading">
                <div>
                  <div className="learner-eyebrow">Progress overview</div>
                  <h2 id="progress-title">Progress summary</h2>
                </div>
              </div>
              <div className="learner-metric-grid">
                <MetricCard icon={<BarChart3 size={20} />} label="Overall progress" value={`${averageProgressValue}%`} />
                <MetricCard icon={<CheckCircle2 size={20} />} label="Completed tasks" value={`${completedTasks}${totalTasks ? ` / ${totalTasks}` : ''}`} />
                <MetricCard icon={<FolderKanban size={20} />} label="Projects in progress" value={`${activeProjects.length}`} />
                <MetricCard icon={<Sparkles size={20} />} label="Skills explored" value={skills.length ? `${skills.length}` : '0'} />
              </div>
            </section>

            <div className="learner-content-grid">
              <section className="learner-section learner-activity-section" aria-labelledby="activity-title">
                <div className="learner-section-heading">
                  <div>
                    <div className="learner-eyebrow">Recent activity</div>
                    <h2 id="activity-title">What you have been working on</h2>
                  </div>
                </div>
                {progressResponse?.recent_activity.length ? <ul className="learner-activity-list">{progressResponse.recent_activity.slice(0, 4).map((activity, index) => <li key={`${activity.task_id ?? activity.project_id ?? 'activity'}-${activity.submitted_at ?? index}`}><span className="learner-activity-mark" aria-hidden="true"><BookOpen size={16} /></span><span className="learner-activity-copy"><strong>{activity.task_title ?? 'Task activity'}</strong><span>{activity.project_name ?? 'Project'}</span></span></li>)}</ul> : <p className="learner-muted">Your recent work will appear here after you start a task.</p>}
              </section>

              <section className="learner-section" id="skills" aria-labelledby="skills-title">
                <div className="learner-section-heading">
                  <div>
                    <div className="learner-eyebrow">What you are building</div>
                    <h2 id="skills-title">Your skills</h2>
                  </div>
                </div>
                {skills.length ? (
                  <div className="learner-skills-list">
                    {skills.map((skill) => <SkillRow key={skill.id} skill={skill} />)}
                  </div>
                ) : (
                  <EmptyState icon={<Sparkles size={22} />} text="Skill progress will appear as you work through project tasks." />
                )}
              </section>
            </div>

            <section className="learner-section learner-discover" aria-labelledby="discover-title">
              <div className="learner-section-heading">
                <div>
                  <div className="learner-eyebrow">Keep exploring</div>
                  <h2 id="discover-title">Available projects</h2>
                </div>
                <ButtonLink className="learner-inline-action" variant="outline" to="/learner/projects">
                  View all projects <ArrowRight size={16} />
                </ButtonLink>
              </div>

              {projectCards.length ? (
                <div className="learner-discover-grid">
                  {projectCards.map(({ project, performance }) => (
                    <article className="learner-discover-card learner-card-with-illustration" key={project.id}>
                      <div className="learner-discover-card-body">
                        <div className="learner-discover-card-top">
                          <span className="learner-mini-badge">{performance && !performance.completed ? 'In progress' : 'Ready to start'}</span>
                          <span className="learner-mini-meta">{performance?.progress ?? 0}%</span>
                        </div>
                        <h3>{project.name}</h3>
                        <p>{project.project_summary}</p>
                        <div className="learner-project-tags">
                          {project.work_areas.slice(0, 3).map((area) => (
                            <span key={`${project.id}-${area.name}`}>{area.name}</span>
                          ))}
                        </div>
                        <Link className="learner-text-link" to={`/learner/projects/${project.id}`}>
                          View project <ArrowRight size={16} />
                        </Link>
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
              ) : currentProject ? (
                <p className="learner-muted">You are up to date. Explore projects to find your next challenge.</p>
              ) : (
                <p className="learner-muted">No published projects are available yet.</p>
              )}
            </section>
          </>
        )}
      </div>
    </main>
  )
}

function MetricCard({ icon, label, value }: { icon: ReactNode; label: string; value: string }) {
  return (
    <article className="learner-metric-card">
      <span className="learner-metric-icon">{icon}</span>
      <span className="learner-metric-label">{label}</span>
      <strong>{value}</strong>
    </article>
  )
}

function SkillRow({ skill }: { skill: SkillProgress }) {
  const score = Math.min(100, Math.max(0, skill.score))

  return (
    <div className="learner-skill-row">
      <div className="learner-skill-heading">
        <span>{skill.name}</span>
        <strong>{score}%</strong>
      </div>
      <div className="learner-progress-track">
        <span style={{ width: `${score}%` }} />
      </div>
    </div>
  )
}

function EmptyState({ icon, text, action, to }: { icon: ReactNode; text: string; action?: string; to?: string }) {
  return (
    <div className="learner-empty-state">
      <span className="learner-empty-icon">{icon}</span>
      <p>{text}</p>
      {action && to && (
        <ButtonLink variant="outline" to={to}>
          {action} <ArrowRight size={16} />
        </ButtonLink>
      )}
    </div>
  )
}

function performanceFromProgress(
  projectId: string,
  progress: LearnerProgressResponse['projects'][number] | undefined,
): ProjectPerformance | null {
  if (!progress) return null

  return {
    project_id: projectId,
    total_tasks: progress.total_tasks,
    completed_tasks: progress.completed_tasks,
    progress: progress.progress,
    completed: progress.completed,
    tasks: [],
    competencies: [],
    concepts: [],
  }
}

function averageProgress(projects: ProjectSnapshot[]) {
  const progressValues = projects.flatMap(({ performance }) => (performance ? [performance.progress] : []))
  if (!progressValues.length) {
    return 0
  }

  return Math.round(progressValues.reduce((total, value) => total + value, 0) / progressValues.length)
}
