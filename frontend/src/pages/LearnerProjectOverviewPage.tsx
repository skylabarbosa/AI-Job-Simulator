import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { CheckCircle2, CircleDot, Clock3 } from 'lucide-react'

import { Button } from '../components/ui/button'
import {
  getBlueprintOverview,
  type BlueprintOverview,
} from '../services/api/blueprints'
import { getApi } from '../services/api/client'
import { startTask } from '../services/api/simulations'
import { getProjectPerformance, type ProjectPerformance } from '../services/api/performance'
import { LearnerTaskWorkspace, type TaskDetail } from './LearnerTaskWorkspacePage'

// ─── Types ───────────────────────────────────────────────────────────────────

interface TaskSummary {
  id: string
  title: string
  description: string | null
  instructions: string | null
  task_type: string
  difficulty: string
  expected_outcome: string | null
  module_id: string | null
  blueprint_task_key: string | null
}

// ─── Component ───────────────────────────────────────────────────────────────

export function LearnerProjectOverviewPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const navigate = useNavigate()
  const [overview, setOverview] = useState<BlueprintOverview | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [overviewRetryCount, setOverviewRetryCount] = useState(0)

  // Work-area selection — navigation only, no DB writes.
  const [selectedWorkArea, setSelectedWorkArea] = useState<string | null>(null)

  // Task list for the selected work area.
  const [tasks, setTasks] = useState<TaskSummary[]>([])
  const [tasksLoading, setTasksLoading] = useState(false)
  const [tasksError, setTasksError] = useState<string | null>(null)

  // The task the learner has clicked into (read-only view before Start Task).
  const [selectedTask, setSelectedTask] = useState<TaskDetail | null>(null)
  const [performance, setPerformance] = useState<ProjectPerformance | null>(null)
  const [performanceError, setPerformanceError] = useState<string | null>(null)
  const [performanceRetryCount, setPerformanceRetryCount] = useState(0)
  const [startingTaskId, setStartingTaskId] = useState<string | null>(null)
  const [startError, setStartError] = useState<string | null>(null)

  useEffect(() => {
    if (!projectId) return
    void getBlueprintOverview(projectId)
      .then(setOverview)
      .catch((requestError) => {
        console.error('Unable to load project overview.', requestError)
        setError('We could not load this project right now.')
      })
      .finally(() => setLoading(false))
  }, [overviewRetryCount, projectId])

  useEffect(() => {
    if (!projectId) return
    void getProjectPerformance(projectId)
      .then(setPerformance)
      .catch((requestError) => {
        console.error('Unable to load learner project progress.', requestError)
        setPerformanceError('Progress is temporarily unavailable.')
      })
  }, [performanceRetryCount, projectId])

  const handleSelectWorkArea = (areaName: string, forceReload = false) => {
    if (selectedWorkArea === areaName && !forceReload) {
      setSelectedWorkArea(null)
      setTasks([])
      setSelectedTask(null)
      return
    }
    setSelectedWorkArea(areaName)
    setSelectedTask(null)
    setTasksLoading(true)
    setTasksError(null)

    if (!projectId) return

    void getApi<TaskSummary[]>(
      `/projects/${projectId}/tasks?module_slug=${encodeURIComponent(
        areaName.toLowerCase().replace(/[^a-z0-9]+/g, '-'),
      )}`,
    )
      .then(setTasks)
      .catch((requestError) =>
        {
          console.error('Unable to load work-area tasks.', requestError)
          setTasksError('We could not load these tasks right now.')
        },
      )
      .finally(() => setTasksLoading(false))
  }

  const handleStartTask = async (task: TaskSummary) => {
    if (!projectId || startingTaskId) return
    setStartError(null)
    setStartingTaskId(task.id)
    try {
      const simulation = await startTask(projectId, task.id)
      void navigate(`/learner/projects/${projectId}/tasks/${task.id}/workspace`, { state: { simulation } })
    } catch (requestError) {
      console.error('Unable to start learner task.', requestError)
      setStartError('We could not start this task. Please try again.')
    } finally {
      setStartingTaskId(null)
    }
  }

  // ─── Guards ──────────────────────────────────────────────────────────────

  if (loading) return <main className="business-shell"><div className="business-state-skeleton" aria-label="Loading project overview"><span /><span /><span /></div></main>
  if (error || !overview)
    return (
      <main className="business-shell">
        <section className="business-content" aria-labelledby="project-load-error-title">
        <h1 id="project-load-error-title">Project unavailable</h1>
        <p className="auth-error" role="alert">
          {error ?? 'Approved project overview not found.'}
        </p>
        <Button onClick={() => { setLoading(true); setError(null); setOverviewRetryCount((count) => count + 1) }}>Retry</Button>
        </section>
      </main>
    )

  // ─── Task workspace (after learner clicks a task) ────────────────────────

  if (selectedTask && projectId) {
    return (
      <main className="business-shell">
        <LearnerTaskWorkspace
          projectId={projectId}
          projectName={overview.project_name}
          task={selectedTask}
          onBack={() => setSelectedTask(null)}
        />
      </main>
    )
  }

  // ─── Project overview + work-area + task selection ───────────────────────

  return (
    <main className="business-shell">
      <section className="business-content learner-overview" aria-labelledby="learner-project-title">
        <nav className="project-breadcrumb" aria-label="Breadcrumb">
          <button type="button" onClick={() => void navigate('/learner/projects')}>Projects</button>
          <span aria-hidden="true">›</span>
          <strong>{overview.project_name}</strong>
        </nav>

        <section className="project-hero" aria-labelledby="learner-project-title">
          <div>
            <div className="auth-eyebrow">Project home</div>
            <h1 id="learner-project-title">{overview.project_name}</h1>
            <p>{overview.project_summary}</p>
            <p className="project-hero-objective">{overview.business_objective}</p>
          </div>
          <div className="project-hero-side" aria-live="polite">
            {performance && <>
              <span className="project-status project-status-active">{performance.completed ? 'Completed' : performance.completed_tasks > 0 ? 'In Progress' : 'Not Started'}</span>
              <strong>{performance.progress}%</strong>
              <span>{performance.completed_tasks} of {performance.total_tasks} tasks complete</span>
              <div className="learner-progress-track" role="progressbar" aria-label="Project progress" aria-valuemin={0} aria-valuemax={100} aria-valuenow={performance.progress}><span style={{ width: `${Math.min(100, Math.max(0, performance.progress))}%` }} /></div>
            </>}
          </div>
        </section>

        <section className="project-journey" aria-labelledby="work-areas-title">
          <div className="project-section-heading">
            <div><div className="auth-eyebrow">Your path</div><h2 id="work-areas-title">Project journey</h2></div>
            {performance && <span className="business-muted">{performance.total_tasks} tasks total</span>}
          </div>
          <ol className="project-journey-list">
            {overview.work_areas.map((area, index) => {
              const areaTasks = overview.assignments.filter((assignment) => assignment.related_work_area === area.name)
              const completedCount = areaTasks.filter((assignment) => performance?.tasks.find((item) => item.task_id === assignment.task_key)?.completed).length
              const isActive = selectedWorkArea === area.name
              const areaStatus = completedCount === areaTasks.length && areaTasks.length > 0 ? 'Completed' : completedCount > 0 ? 'In Progress' : 'Not Started'
              const StatusIcon = areaStatus === 'Completed' ? CheckCircle2 : areaStatus === 'In Progress' ? Clock3 : CircleDot
              return <li className={`project-journey-item${isActive ? ' project-journey-item-active' : ''}`} key={area.name}>
                <button type="button" onClick={() => handleSelectWorkArea(area.name)} aria-pressed={isActive}>
                  <span className="project-journey-number">{String(index + 1).padStart(2, '0')}</span>
                  <span className="project-journey-copy"><strong>{area.name}</strong><small><StatusIcon aria-hidden="true" /> {areaStatus}</small></span>
                  <span className="project-journey-count">{areaTasks.length} {areaTasks.length === 1 ? 'task' : 'tasks'}</span>
                </button>
              </li>
            })}
          </ol>
        </section>

        <article className="blueprint-block overview-progress" aria-live="polite">
          <h2>Project goal</h2>
          <p>{overview.overall_expected_outcome}</p>
          {performanceError && (
            <div className="learner-alert" role="alert">
              <p>{performanceError}</p>
              <Button variant="outline" onClick={() => { setPerformanceError(null); setPerformanceRetryCount((count) => count + 1) }}>Retry</Button>
            </div>
          )}
          {!performanceError && !performance && <p className="business-muted">Loading project progress...</p>}
        </article>

        <section className="project-task-queue" aria-labelledby="task-queue-title">
          <div className="project-section-heading">
            <div><div className="auth-eyebrow">Work queue</div><h2 id="task-queue-title">{selectedWorkArea ? selectedWorkArea : 'Choose a work area'}</h2></div>
            {selectedWorkArea && <span className="business-muted">{tasks.length} tasks</span>}
          </div>
          {overview.work_areas.length === 0 && <p className="business-muted">Work areas will appear here when this project is ready.</p>}
          {!selectedWorkArea && <p className="business-muted">Select a step above to see its tasks.</p>}

          {/* ── Task list for the selected work area ── */}
          {selectedWorkArea && (
            <div
              style={{ marginTop: '1.5rem' }}
              aria-live="polite"
              aria-label={`Tasks for ${selectedWorkArea}`}
            >
              {tasksLoading && (
                <p className="business-muted">Loading tasks...</p>
              )}
              {tasksError && (
                <div className="learner-alert" role="alert">
                  <p>{tasksError}</p>
                  <Button variant="outline" onClick={() => handleSelectWorkArea(selectedWorkArea, true)}>Retry</Button>
                </div>
              )}
              {startError && <p className="auth-error" role="alert">{startError}</p>}
              {!tasksLoading && !tasksError && tasks.length === 0 && (
                <p className="business-muted">No tasks found for this work area.</p>
              )}

              <div className="task-queue-list">
                {tasks.map((task) => (
                  <article className="task-queue-item" key={task.id}>
                    <span className="task-queue-number">{String(tasks.indexOf(task) + 1).padStart(2, '0')}</span>
                    <div className="task-queue-copy"><h3>{task.title}</h3>
                    {performance && (
                      <p className="task-status-text">{performance.tasks.find((item) => item.task_id === task.id)?.completed ? 'Completed' : 'Not Started'}</p>
                    )}
                    {task.description && <p>{task.description}</p>}
                    </div>
                    <Button
                      id={`task-btn-${task.id}`}
                      variant={performance?.tasks.find((item) => item.task_id === task.id)?.completed ? 'outline' : 'default'}
                      onClick={() => void handleStartTask(task)}
                      disabled={startingTaskId !== null}
                      aria-busy={startingTaskId === task.id}
                    >
                      {startingTaskId === task.id ? 'Opening...' : performance?.tasks.find((item) => item.task_id === task.id)?.completed ? 'Review' : 'Start Task'}
                    </Button>
                  </article>
                ))}
              </div>
            </div>
          )}
        </section>

      </section>
    </main>
  )
}

