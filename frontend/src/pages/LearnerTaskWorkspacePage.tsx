import { useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Check, ChevronDown, ChevronRight, Database, Lightbulb, LockKeyhole, Play, Send } from 'lucide-react'

import { Button, ButtonLink } from '../components/ui/button'
import {
  getDatasetDownloadUrl,
  getDatasetPreview,
  listDatasets,
  type Dataset,
  type DatasetPreview,
} from '../services/api/datasets'
import {
  getAdaptiveDecision,
  type AdaptivePresentationDecision,
} from '../services/api/adaptive'
import { startTask, type SimulationContext } from '../services/api/simulations'
import { checkTaskWork, submitTaskWork, type SubmissionResult } from '../services/api/submissions'
import { getTaskEvaluation } from '../services/api/performance'
import { ApiError } from '../services/api/client'
import {
  exampleApproachForTask,
  getTaskPresentation,
  hintForTask,
  resolveWorkspacePresentation,
} from './adaptiveWorkspacePresentation'

export interface TaskDetail {
  id: string
  title: string
  description: string | null
  instructions: string | null
  task_type: string
  difficulty: string
  expected_outcome: string | null
  module_name: string
}

interface LearnerTaskWorkspaceProps {
  projectId: string
  projectName: string
  task: TaskDetail
  onBack: () => void
}

export function LearnerTaskWorkspace({
  projectId,
  projectName,
  task,
  onBack,
}: LearnerTaskWorkspaceProps) {
  const [starting, setStarting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()

  const handleStart = async () => {
    if (starting) return
    setError(null)
    setStarting(true)
    try {
      const simulation = await startTask(projectId, task.id)
      void navigate(`/learner/projects/${projectId}/tasks/${task.id}/workspace`, {
        state: { simulation },
      })
    } catch (requestError) {
      console.error('Unable to start learner task.', requestError)
      setError(
        'We could not start this task. Please try again.',
      )
    } finally {
      setStarting(false)
    }
  }

  return (
    <section className="business-content" aria-labelledby="task-workspace-title">
      <button
        type="button"
        className="business-back-link"
        style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
        onClick={onBack}
      >
        Back to work area
      </button>

      <div className="auth-eyebrow">{projectName} / {task.module_name}</div>
      <h1 id="task-workspace-title">{task.title}</h1>

      {task.description && <p>{task.description}</p>}

      {task.instructions && (
        <article className="blueprint-block" aria-labelledby="instructions-heading">
          <h3 id="instructions-heading">Instructions</h3>
          <p style={{ whiteSpace: 'pre-wrap' }}>{task.instructions}</p>
        </article>
      )}

      {task.expected_outcome && (
        <article className="blueprint-block">
          <h3>Expected outcome</h3>
          <p>{task.expected_outcome}</p>
        </article>
      )}

      {error && (
        <p className="auth-error" role="alert">
          {error}
        </p>
      )}

      <div className="project-card-actions" style={{ marginTop: '1.5rem' }}>
        <Button
          id="start-task-btn"
          onClick={() => void handleStart()}
          disabled={starting}
          aria-busy={starting}
        >
          {starting ? 'Starting...' : 'Start Task'}
        </Button>
      </div>
    </section>
  )
}

interface WorkspaceLocationState {
  simulation?: SimulationContext
}

export function LearnerStartedTaskWorkspacePage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { projectId, taskId } = useParams<{ projectId: string; taskId: string }>()
  const state = (location.state ?? {}) as WorkspaceLocationState
  const initialSimulation = state.simulation ?? null
  const [simulation, setSimulation] = useState<SimulationContext | null>(initialSimulation)
  const [loadingSimulation, setLoadingSimulation] = useState(
    !initialSimulation && Boolean(projectId && taskId),
  )
  const [simulationError, setSimulationError] = useState<string | null>(null)
  const [simulationRetryCount, setSimulationRetryCount] = useState(0)
  const [evaluationRestoreError, setEvaluationRestoreError] = useState<string | null>(null)
  const [evaluationRetryCount, setEvaluationRetryCount] = useState(0)
  const [adaptiveDecision, setAdaptiveDecision] = useState<AdaptivePresentationDecision | null>(null)
  const [work, setWork] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [checking, setChecking] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [runError, setRunError] = useState<string | null>(null)
  const [submissionResult, setSubmissionResult] = useState<SubmissionResult | null>(null)
  const [runResult, setRunResult] = useState<SubmissionResult | null>(null)
  const [hintLevel, setHintLevel] = useState(0)
  const [datasets, setDatasets] = useState<Dataset[]>([])
  const [datasetsLoading, setDatasetsLoading] = useState(false)
  const [datasetsError, setDatasetsError] = useState<string | null>(null)
  const [datasetsRetryCount, setDatasetsRetryCount] = useState(0)
  const [openingDatasetId, setOpeningDatasetId] = useState<string | null>(null)
  const [openError, setOpenError] = useState<string | null>(null)
  const [previewDatasetId, setPreviewDatasetId] = useState<string | null>(null)
  const [preview, setPreview] = useState<DatasetPreview | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [previewError, setPreviewError] = useState<string | null>(null)
  const startRequestKey = useRef<string | null>(null)
  const workInputRef = useRef<HTMLTextAreaElement | null>(null)
  const gutterLinesRef = useRef<HTMLDivElement | null>(null)

  const effectiveProjectId = simulation?.project_id || projectId
  const evaluationProjectId = simulation?.project_id
  const evaluationTaskId = simulation?.task_id

  useEffect(() => {
    if (simulation || !projectId || !taskId) return

    const requestKey = `${projectId}:${taskId}:${simulationRetryCount}`
    if (startRequestKey.current === requestKey) return
    startRequestKey.current = requestKey

    setLoadingSimulation(true)
    setSimulationError(null)
    void startTask(projectId, taskId)
      .then(setSimulation)
      .catch((requestError) => {
        console.error('Unable to resume learner task workspace.', requestError)
        setSimulationError('We could not open this task right now.')
      })
      .finally(() => setLoadingSimulation(false))
  }, [projectId, simulation, simulationRetryCount, taskId])

  useEffect(() => {
    if (!simulation) {
      setAdaptiveDecision(null)
      return
    }

    let current = true
    setAdaptiveDecision(null)
    void getAdaptiveDecision(simulation.project_id, simulation.task_id)
      .then((decision) => {
        if (current) setAdaptiveDecision(decision)
      })
      .catch(() => {
        // The normal workspace remains available when read-only adaptation is unavailable.
        console.error('Optional task guidance could not be loaded.')
        if (current) setAdaptiveDecision(null)
      })

    return () => {
      current = false
    }
  }, [simulation])

  // Results are durable server records, not only transient workspace state.
  useEffect(() => {
    if (!evaluationProjectId || !evaluationTaskId) return
    let current = true
    void getTaskEvaluation(evaluationProjectId, evaluationTaskId)
      .then((evaluation) => {
        if (!current) return
        setEvaluationRestoreError(null)
        if (!evaluation) return
        setSubmissionResult({
          submission_id: evaluation.submission_id,
          evaluation_id: null,
          validation_status: evaluation.status === 'completed' && evaluation.score === 100
            ? 'passed'
            : evaluation.status === 'completed' ? 'failed' : 'needs_evaluation',
          message: evaluation.feedback ?? 'Your latest evaluation was restored.',
          checks: [],
          strengths: evaluation.strengths ?? [],
          areas_for_improvement: evaluation.areas_for_improvement ?? [],
          evidence: evaluation.evidence ?? [],
          skill_evidence: [],
          execution_status: null,
          columns: [],
          rows: [],
          row_count: null,
          displayed_row_count: null,
          truncated: false,
          execution_time_ms: null,
        })
      })
      .catch((requestError: unknown) => {
        if (current) {
          console.error('Unable to restore learner feedback.', requestError)
          setEvaluationRestoreError('Your latest feedback could not be loaded.')
        }
      })
    return () => { current = false }
  }, [evaluationProjectId, evaluationRetryCount, evaluationTaskId])

  useEffect(() => {
    if (!effectiveProjectId) return

    setDatasetsLoading(true)
    setDatasetsError(null)
    void listDatasets(effectiveProjectId)
      .then(setDatasets)
      .catch((requestError) => {
        console.error('Unable to load learner resources.', requestError)
        setDatasetsError('We could not load project resources right now.')
      })
      .finally(() => setDatasetsLoading(false))
  }, [datasetsRetryCount, effectiveProjectId])

  if (loadingSimulation) {
    return <main className="business-shell"><div className="business-state-skeleton" aria-label="Opening task workspace"><span /><span /><span /></div></main>
  }

  if (simulationError || !simulation) {
    return (
      <main className="business-shell">
        <section className="business-content" aria-labelledby="workspace-error-title">
        <h1 id="workspace-error-title">Task unavailable</h1>
        <p className="auth-error" role="alert">
          {simulationError ?? 'Start a task before opening the workspace.'}
        </p>
        {simulationError && projectId && taskId && (
          <Button onClick={() => { setLoadingSimulation(true); setSimulationError(null); setSimulationRetryCount((count) => count + 1) }}>Retry</Button>
        )}
        <Button onClick={() => void navigate('/learner/projects')}>Back to projects</Button>
        </section>
      </main>
    )
  }

  const handleSubmit = async () => {
    if (submitting) return
    setSubmitError(null)
    setSubmissionResult(null)
    setSubmitting(true)
    try {
      const contentKey = simulation.task_type.toLowerCase() === 'sql' ? 'sql' : 'response'
      const result = await submitTaskWork(simulation.project_id, simulation.task_id, work, {
        [contentKey]: work,
        task_type: simulation.task_type,
        simulation_id: simulation.simulation_id,
      })
      setSubmissionResult(result)
    } catch (requestError) {
      console.error('Unable to submit learner work.', requestError)
      setSubmitError('We could not submit your work. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  const canSubmit = work.trim().length > 0 && !submitting
  const taskPresentation = getTaskPresentation(simulation.task_type)
  const isSqlTask = taskPresentation.editorMode === 'sql'
  const canRun = work.trim().length > 0 && !checking && !submitting
  const presentation = resolveWorkspacePresentation(simulation, adaptiveDecision)
  const hasTaskRequirements = Boolean(simulation.task_instructions || simulation.task_expected_outcome)

  const handleRunCheck = async () => {
    if (!canRun) return

    setRunError(null)
    setRunResult(null)
    setChecking(true)

    try {
      const contentKey = isSqlTask ? 'sql' : 'response'
      const result = await checkTaskWork(simulation.project_id, simulation.task_id, work, {
        [contentKey]: work,
        task_type: simulation.task_type,
        simulation_id: simulation.simulation_id,
      })
      const safetyResult = isSqlTask
        ? result
        : {
            ...result,
            message: result.checks.length > 0 ? result.message : 'Your response is ready to submit.',
          }
      setRunResult(safetyResult)
    } catch (requestError) {
      console.error('Unable to run learner task checks.', requestError)
      setRunError(requestError instanceof ApiError && requestError.detail
        ? requestError.detail
        : isSqlTask
          ? 'We could not run your SQL right now. Please try again.'
          : 'We could not validate your response right now. Please try again.')
    } finally {
      setChecking(false)
    }
  }

  const handleOpenDataset = async (dataset: Dataset) => {
    if (openingDatasetId || !effectiveProjectId) return
    setOpenError(null)
    setOpeningDatasetId(dataset.id)
    try {
      const { url } = await getDatasetDownloadUrl(effectiveProjectId, dataset.id)
      window.open(url, '_blank', 'noopener,noreferrer')
    } catch (requestError) {
      console.error('Unable to open learner resource.', requestError)
      setOpenError('We could not open this resource. Please try again.')
    } finally {
      setOpeningDatasetId(null)
    }
  }

  const handlePreviewDataset = async (dataset: Dataset) => {
    if (previewLoading || !effectiveProjectId) return
    setPreviewDatasetId(dataset.id)
    setPreview(null)
    setPreviewError(null)
    setPreviewLoading(true)
    try {
      const result = await getDatasetPreview(effectiveProjectId, dataset.id, 10)
      setPreview(result)
    } catch (requestError) {
      console.error('Unable to preview learner dataset.', requestError)
      setPreviewError('We could not load this preview. Please try again.')
    } finally {
      setPreviewLoading(false)
    }
  }

  return (
    <main className="business-shell">
      <section className="business-content task-workspace" aria-labelledby="active-task-title">
        <header className="workspace-mobile-header">
          <button type="button" onClick={() => void navigate(`/learner/projects/${simulation.project_id}`)} aria-label="Back to work area">
            <ArrowLeft aria-hidden="true" />
            <span>Back to tasks</span>
          </button>
          <strong>{simulation.task_title}</strong>
        </header>
        <nav className="workspace-breadcrumb" aria-label="Breadcrumb">
          <button type="button" onClick={() => void navigate('/learner/projects')}>Projects</button>
          <ChevronRight aria-hidden="true" />
          <span className="workspace-breadcrumb-middle">{simulation.project_name} <ChevronRight aria-hidden="true" /> {simulation.module_name} <ChevronRight aria-hidden="true" /></span>
          <strong>{simulation.task_title}</strong>
        </nav>

        <div className="workspace-heading">
          <div>
            <p className="auth-eyebrow">{simulation.module_name}</p>
            <h1 id="active-task-title">{simulation.task_title}</h1>
          </div>
          <p className="workspace-task-counter">Current task · {simulation.module_name}</p>
        </div>

        {simulation.task_description && <p>{simulation.task_description}</p>}

        {hasTaskRequirements && (
          <article className="blueprint-block task-brief" aria-labelledby="task-brief-heading">
            <h2 id="task-brief-heading">Task instructions</h2>
            {simulation.task_instructions && <p style={{ whiteSpace: 'pre-wrap' }}>{simulation.task_instructions}</p>}
            {simulation.task_expected_outcome && (
              <div className="task-requirements">
                <h3>Requirements</h3>
                <p><Check aria-hidden="true" /> {simulation.task_expected_outcome}</p>
              </div>
            )}
          </article>
        )}

        {evaluationRestoreError && (
          <div className="learner-alert" role="alert">
            <p>{evaluationRestoreError}</p>
            <Button variant="outline" onClick={() => { setEvaluationRestoreError(null); setEvaluationRetryCount((count) => count + 1) }}>Retry</Button>
          </div>
        )}

        <div className="workspace-grid">
          <div className="workspace-main-column">
          <article className="blueprint-block workspace-editor" aria-labelledby="editor-heading">
            <div className="workspace-panel-heading">
              <div>
                <div className="workspace-editor-heading-row">
                  <h2 id="editor-heading">{taskPresentation.editor.heading}</h2>
                  <span className="workspace-task-type" aria-label={`Task type: ${taskPresentation.editor.taskTypeLabel}`}>
                    {taskPresentation.editor.taskTypeLabel}
                    <ChevronDown aria-hidden="true" />
                  </span>
                </div>
              </div>
            </div>
            <label>
              <span className="sr-only">{taskPresentation.editor.ariaLabel}</span>
              <div className={`code-editor-shell ${taskPresentation.editor.shellClassName}`}>
                {taskPresentation.editor.showGutter && (
                  <div className="code-gutter" aria-hidden="true">
                    <div ref={gutterLinesRef} className="code-gutter-lines">
                      {(work || ' ').split('\n').map((_, index) => <span key={index}>{index + 1}</span>)}
                    </div>
                  </div>
                )}
                <textarea
                  className={isSqlTask ? 'code-input' : 'response-input'}
                  ref={workInputRef}
                  value={work}
                  onChange={(event) => {
                    const nextValue = event.target.value
                    setWork(nextValue)
                    if (runError || runResult) {
                      setRunError(null)
                      setRunResult(null)
                    }
                  }}
                  onScroll={(event) => {
                    if (gutterLinesRef.current) {
                      gutterLinesRef.current.style.transform = `translateY(-${event.currentTarget.scrollTop}px)`
                    }
                  }}
                  rows={isSqlTask ? 14 : 12}
                  placeholder={taskPresentation.editor.placeholder}
                  disabled={submitting}
                  spellCheck={taskPresentation.editor.spellCheck}
                  required
                  aria-label={taskPresentation.editor.ariaLabel}
                />
              </div>
            </label>

            {submitError && (
              <p className="auth-error" role="alert">
                {submitError}
              </p>
            )}

            <div className="workspace-action-row">
              <Button
                className="run-action"
                onClick={() => void handleRunCheck()}
                disabled={!canRun}
                aria-busy={checking}
                title={taskPresentation.primaryAction.title}
              >
                <Play aria-hidden="true" /> {checking ? (isSqlTask ? 'Running...' : 'Checking...') : taskPresentation.primaryAction.label}
              </Button>
              <span className="workspace-action-note">
                {taskPresentation.primaryAction.description}
              </span>
            </div>
            {runError && <p className="auth-error" role="alert">{runError}</p>}
          </article>

          <article className="blueprint-block workspace-results" aria-labelledby="results-heading" aria-live="polite">
            <div className="workspace-panel-heading">
              <div>
                <p className="auth-eyebrow">{isSqlTask ? 'Run output' : 'Check output'}</p>
                <h2 id="results-heading">{taskPresentation.results.heading}</h2>
              </div>
              <span className="results-status">
                {checking ? (isSqlTask ? 'Running...' : 'Checking...') : runError ? 'Error' : runResult ? (runResult.validation_status === 'failed' ? 'Needs attention' : taskPresentation.results.readyState) : (isSqlTask ? 'Not run' : 'Not checked')}
              </span>
            </div>
            {checking && <p className="workspace-empty-state">{isSqlTask ? 'Running your SQL...' : 'Checking your response...'}</p>}
            {!checking && runError && <p className="workspace-empty-state">{runError}</p>}
            {!checking && !runError && runResult && (
              <>
                <p className="workspace-empty-state">{isSqlTask ? runResult.message : (runResult.checks.length > 0 ? runResult.message : 'Your response is ready to submit.')}</p>
                {isSqlTask && runResult.execution_status === 'success' && (
                  <>
                    <div className="workspace-result-meta">
                      <span>{runResult.row_count ?? 0} row{runResult.row_count === 1 ? '' : 's'}</span>
                      {runResult.execution_time_ms !== null && <span>{runResult.execution_time_ms} ms</span>}
                    </div>
                    {runResult.truncated && <p className="workspace-result-notice">Showing the first {runResult.displayed_row_count} rows.</p>}
                    {runResult.columns.length > 0 && (
                      <div className="workspace-table-wrap">
                        <table className="workspace-result-table">
                          <thead><tr>{runResult.columns.map((column) => <th key={column}>{column}</th>)}</tr></thead>
                          <tbody>
                            {runResult.rows.map((row, rowIndex) => (
                              <tr key={rowIndex}>{row.map((value, columnIndex) => <td key={`${rowIndex}-${columnIndex}`}>{value === null ? 'NULL' : String(value)}</td>)}</tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </>
                )}
                {runResult.checks.length > 0 && (
                  <ul className="evaluation-check-list">
                    {runResult.checks.map((check) => (
                      <li key={`${check.name}-${check.message}`}>
                        <span aria-hidden="true">{check.passed ? '✓' : '•'}</span>
                        <span><strong>{check.name}</strong>{check.message && <>: {check.message}</>}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </>
            )}
            {!checking && !runError && !runResult && (
              <p className="workspace-empty-state">
                {isSqlTask ? 'Write a query first.' : 'Check your response before submitting it for review.'}
              </p>
            )}
          </article>

          {submissionResult && (
            <article className={`blueprint-block validation-result validation-result-${submissionResult.validation_status}`} aria-live="polite" aria-labelledby="evaluation-heading">
              <div className="evaluation-result-heading">
                <div>
                  <p className="result-status">
                    {submissionResult.validation_status === 'passed' ? 'Task complete' : submissionResult.validation_status === 'failed' ? 'Keep working' : 'Review in progress'}
                  </p>
                  <h2 id="evaluation-heading">{simulation.task_title}</h2>
                </div>
                {submissionResult.validation_status === 'passed' ? <Check aria-label="Completed" /> : <Lightbulb aria-label="Feedback" />}
              </div>
              <p className="evaluation-feedback">{submissionResult.message}</p>
              {submissionResult.validation_status === 'failed' && <h3>What to check</h3>}
              {submissionResult.areas_for_improvement.length > 0 && <><h3>Next steps</h3><ul>{submissionResult.areas_for_improvement.map((area) => <li key={area}>{area}</li>)}</ul></>}
              {submissionResult.strengths.length > 0 && <><h3>What you did well</h3><ul>{submissionResult.strengths.map((strength) => <li key={strength}>{strength}</li>)}</ul></>}
              {submissionResult.checks.length > 0 && <><h3>Checks</h3><ul className="evaluation-check-list">{submissionResult.checks.map((check) => <li key={check.name}><span aria-hidden="true">{check.passed ? '✓' : '•'}</span><span><strong>{check.name}</strong>{check.message && <>: {check.message}</>}</span></li>)}</ul></>}
              {submissionResult.evidence.length > 0 && <><h3>Evidence</h3><ul>{submissionResult.evidence.map((item) => <li key={item}>{item}</li>)}</ul></>}
              <div className="evaluation-actions">
                {submissionResult.validation_status === 'failed' && <Button variant="outline" onClick={() => workInputRef.current?.focus()}>Try again</Button>}
                <ButtonLink to={`/learner/projects/${simulation.project_id}`}>
                  {submissionResult.validation_status === 'passed' ? 'Continue to project' : 'Back to work area'} <ChevronRight aria-hidden="true" />
                </ButtonLink>
              </div>
            </article>
          )}

          </div>

          <aside className="blueprint-block workspace-resources" aria-labelledby="resources-heading">
            <div className="workspace-panel-heading"><div><p className="auth-eyebrow">Reference</p><h2 id="resources-heading">Dataset</h2></div><Database aria-hidden="true" /></div>

            {datasetsLoading && <div className="resource-skeleton" aria-live="polite">Loading project resources...</div>}
            {datasetsError && (
              <div className="learner-alert" role="alert">
                <p>{datasetsError}</p>
                <Button variant="outline" onClick={() => { setDatasetsLoading(true); setDatasetsError(null); setDatasetsRetryCount((count) => count + 1) }}>Retry</Button>
              </div>
            )}
            {openError && <p className="auth-error" role="alert">{openError}</p>}
            {!datasetsLoading && !datasetsError && datasets.length === 0 && (
              <p className="business-muted">No project resources are available for this task.</p>
            )}

            {datasets.map((dataset) => (
              <div className="resource-item" key={dataset.id}>
                <h3>{dataset.file_name}</h3>
                <p className="business-muted">
                  {dataset.status === 'ready' ? 'Ready to use' : dataset.status === 'pending' ? 'Preparing' : 'Unavailable'} · {dataset.row_count ?? 0} rows · {dataset.column_count ?? 0} columns
                </p>
                {dataset.schema_metadata.columns && dataset.schema_metadata.columns.length > 0 && <div className="schema-section"><h3>Columns</h3><dl>{dataset.schema_metadata.columns.map((column) => <div key={column.name}><dt>{column.name}</dt><dd>{column.inferred_type || 'Type unavailable'}</dd></div>)}</dl></div>}
                <div className="project-card-actions">
                  {dataset.status === 'ready' ? (
                    <>
                      <Button
                        variant="outline"
                        onClick={() => void handlePreviewDataset(dataset)}
                        disabled={previewLoading}
                        aria-busy={previewLoading && previewDatasetId === dataset.id}
                      >
                        {previewLoading && previewDatasetId === dataset.id ? 'Loading...' : 'Preview'}
                      </Button>
                      <Button
                        variant="outline"
                        onClick={() => void handleOpenDataset(dataset)}
                        disabled={openingDatasetId !== null}
                        aria-busy={openingDatasetId === dataset.id}
                      >
                        {openingDatasetId === dataset.id ? 'Opening...' : 'Open'}
                      </Button>
                    </>
                  ) : (
                    <span className="business-muted">Unavailable</span>
                  )}
                </div>
              </div>
            ))}

            {((presentation.mode === 'guided' && (presentation.showHints || presentation.showExamples)) ||
              (presentation.mode === 'standard' && (presentation.showHints || presentation.showExamples))) && (
              <details className="adaptive-guidance">
                <summary><Lightbulb aria-hidden="true" /> {presentation.helpLabel ?? 'Optional help'}</summary>
                {presentation.explanation && <p>{presentation.explanation}</p>}
                {presentation.guidedSteps.length > 0 && <ol>{presentation.guidedSteps.map((step) => <li key={step}>{step}</li>)}</ol>}
                {presentation.showHints && (
                  <div className="hint-stage">
                    <button type="button" className="hint-trigger ui-primary-button" onClick={() => setHintLevel((level) => Math.max(level, 1))}>
                      <Lightbulb aria-hidden="true" /> Hint 1
                    </button>
                    {hintLevel >= 1 ? <p>{hintForTask(simulation.task_type)}</p> : <p className="business-muted">A conceptual nudge to help you choose your next step.</p>}
                  </div>
                )}
                {presentation.showHints && hintLevel < 1 && <p className="hint-locked"><LockKeyhole aria-hidden="true" /> Hint 2 · Unlock after viewing Hint 1</p>}
                {presentation.showHints && hintLevel >= 1 && <div className="hint-stage"><button type="button" className="hint-trigger ui-primary-button" onClick={() => setHintLevel((level) => Math.max(level, 2))}><Lightbulb aria-hidden="true" /> Hint 2</button>{hintLevel >= 2 ? <p>{exampleApproachForTask(simulation.task_type)}</p> : <p className="hint-locked"><LockKeyhole aria-hidden="true" /> Unlock after viewing Hint 1</p>}</div>}
                {presentation.showExamples && <p className="hint-locked"><LockKeyhole aria-hidden="true" /> Example · Available after viewing Hint 2</p>}
              </details>
            )}
          </aside>
        </div>

        <div className="workspace-submit-row">
          <Button onClick={() => void handleSubmit()} disabled={!canSubmit} aria-busy={submitting} className="submit-task-action">
            <Send aria-hidden="true" /> {submitting ? 'Submitting...' : 'Submit Task'}
          </Button>
          <span className="workspace-action-note">Submit sends your work for review.</span>
        </div>

        <div className="workspace-mobile-actions" aria-label="Workspace actions">
          <Button
            variant="outline"
            className="run-action"
            onClick={() => void handleRunCheck()}
            disabled={!canRun}
            aria-busy={checking}
            title={taskPresentation.primaryAction.title}
          >
            <Play aria-hidden="true" /> {checking ? (isSqlTask ? 'Running...' : 'Checking...') : taskPresentation.primaryAction.label}
          </Button>
          <Button onClick={() => void handleSubmit()} disabled={!canSubmit} aria-busy={submitting} className="submit-task-action">
            <Send aria-hidden="true" /> {submitting ? 'Submitting...' : 'Submit Task'}
          </Button>
        </div>

        <article className="blueprint-block dataset-preview" aria-labelledby="preview-heading">
          <h2 id="preview-heading">Dataset preview</h2>
          {!previewDatasetId && !previewLoading && !previewError && (
            <p className="business-muted">Choose Preview on an available dataset to load real rows.</p>
          )}
          {previewLoading && <p className="business-muted">Loading dataset preview...</p>}
          {previewError && (
            <div className="learner-alert" role="alert">
              <p>{previewError}</p>
              <Button variant="outline" onClick={() => {
                const dataset = datasets.find((item) => item.id === previewDatasetId)
                if (dataset) void handlePreviewDataset(dataset)
              }}>Retry</Button>
            </div>
          )}
          {preview && preview.rows.length === 0 && (
            <p className="business-muted">This dataset has no preview rows.</p>
          )}
          {preview && preview.rows.length > 0 && (
            <div className="preview-table-wrap">
              <p className="business-muted">
                    {preview.file_name} · showing {preview.rows.length} of {preview.total_rows ?? 'available'} rows
              </p>
              <table className="preview-table">
                <thead>
                  <tr>
                    {preview.columns.map((column) => (
                      <th key={column}>{column}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {preview.rows.map((row, index) => (
                    <tr key={`${preview.dataset_id}-${index}`}>
                      {preview.columns.map((column) => (
                        <td key={column}>{row[column]}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </article>
      </section>
    </main>
  )
}
