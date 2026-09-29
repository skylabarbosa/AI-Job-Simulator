import { useEffect, useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'

import { Button } from '../components/ui/button'
import { BusinessAppShell } from '../components/BusinessAppShell'
import { approveBlueprint, generateBlueprint, getBlueprint, materializeBlueprint, reviseBlueprint, updateBlueprint, type BlueprintRecord, type MaterializationResult, type ProjectBlueprint } from '../services/api/blueprints'
import { deleteDataset, getDatasetDownloadUrl, listDatasets, uploadDataset, type Dataset } from '../services/api/datasets'
import { archiveProject, getProject, publishProject, updateProject, type Project, type ProjectInput } from '../services/api/projects'
import { canPublishProject } from './projectPublishing'

function projectInput(project: Project): ProjectInput {
  return {
    name: project.name,
    business_problem: project.business_problem ?? '',
    work_requirements: project.work_requirements ?? '',
    desired_outcome: project.desired_outcome ?? '',
  }
}

export function ProjectDetailPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const [project, setProject] = useState<Project | null>(null)
  const [datasets, setDatasets] = useState<Dataset[]>([])
  const [form, setForm] = useState<ProjectInput | null>(null)
  const [editing, setEditing] = useState(false)
  const [loading, setLoading] = useState(true)
  const [projectRetryCount, setProjectRetryCount] = useState(0)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [datasetError, setDatasetError] = useState<string | null>(null)
  const [datasetsLoading, setDatasetsLoading] = useState(true)
  const [datasetRetryCount, setDatasetRetryCount] = useState(0)
  const [datasetSubmitting, setDatasetSubmitting] = useState(false)
  const [blueprint, setBlueprint] = useState<BlueprintRecord | null>(null)
  const [blueprintLoading, setBlueprintLoading] = useState(true)
  const [blueprintSubmitting, setBlueprintSubmitting] = useState(false)
  const [blueprintError, setBlueprintError] = useState<string | null>(null)
  const [blueprintRetryCount, setBlueprintRetryCount] = useState(0)
  const [materialization, setMaterialization] = useState<MaterializationResult | null>(null)
  const [publishing, setPublishing] = useState(false)
  const [editingBlueprint, setEditingBlueprint] = useState(false)
  const [blueprintDraftForm, setBlueprintDraftForm] = useState<ProjectBlueprint | null>(null)

  useEffect(() => {
    if (!projectId) return
    setLoading(true)
    void getProject(projectId)
      .then((loadedProject) => {
        setProject(loadedProject)
        setForm(projectInput(loadedProject))
      })
      .catch((requestError) => {
        console.error('Unable to load business project.', requestError)
        setError('We could not load this project right now.')
      })
      .finally(() => setLoading(false))
  }, [projectId, projectRetryCount])

  useEffect(() => {
    if (!projectId) return
    setDatasetsLoading(true)
    setDatasetError(null)
    void listDatasets(projectId)
      .then(setDatasets)
      .catch((requestError) => {
        console.error('Unable to load project datasets.', requestError)
        setDatasetError('We could not load datasets right now.')
      })
      .finally(() => setDatasetsLoading(false))
  }, [datasetRetryCount, projectId])

  useEffect(() => {
    if (!projectId) return
    setBlueprintLoading(true)
    setBlueprintError(null)
    void getBlueprint(projectId)
      .then((loadedBlueprint) => {
        setBlueprint(loadedBlueprint)
        if (loadedBlueprint?.status === 'draft') setBlueprintDraftForm(loadedBlueprint.blueprint_json)
      })
      .catch((requestError) => {
        console.error('Unable to load project blueprint.', requestError)
        setBlueprintError('We could not load the blueprint right now.')
      })
      .finally(() => setBlueprintLoading(false))
  }, [blueprintRetryCount, projectId])

  const handleGenerateBlueprint = async () => {
    if (!projectId) return
    setBlueprintError(null)
    setBlueprintSubmitting(true)
    try {
      const generated = await generateBlueprint(projectId, Boolean(blueprint))
      setBlueprint(generated)
      if (generated.status === 'draft') setBlueprintDraftForm(generated.blueprint_json)
    } catch (requestError) {
      console.error('Unable to generate blueprint.', requestError)
      setBlueprintError('Blueprint generation is temporarily unavailable. Please try again.')
    } finally {
      setBlueprintSubmitting(false)
    }
  }

  const handleReviseBlueprint = async () => {
    if (!projectId || !blueprint || blueprint.status !== 'approved') return
    setBlueprintError(null)
    setBlueprintSubmitting(true)
    try {
      const revised = await reviseBlueprint(projectId)
      setBlueprint(revised)
      setBlueprintDraftForm(revised.blueprint_json)
      setEditingBlueprint(true)
    } catch (requestError) {
      console.error('Unable to create blueprint revision.', requestError)
      setBlueprintError('We could not create a revision right now. Please try again.')
    } finally {
      setBlueprintSubmitting(false)
    }
  }

  const handleSaveBlueprintDraft = async (e: FormEvent) => {
    e.preventDefault()
    if (!projectId || !blueprint || blueprint.status !== 'draft' || !blueprintDraftForm) return
    setBlueprintError(null)
    setBlueprintSubmitting(true)
    try {
      const updated = await updateBlueprint(projectId, blueprint.id, blueprintDraftForm)
      setBlueprint(updated)
      setEditingBlueprint(false)
    } catch (requestError) {
      console.error('Unable to update blueprint draft.', requestError)
      setBlueprintError('We could not save these blueprint changes. Please try again.')
    } finally {
      setBlueprintSubmitting(false)
    }
  }

  const handleApproveBlueprint = async () => {
    if (!projectId || !blueprint || blueprint.status !== 'draft') return
    setBlueprintError(null)
    setBlueprintSubmitting(true)
    try {
      setBlueprint(await approveBlueprint(projectId, blueprint.id))
      setEditingBlueprint(false)
    } catch (requestError) {
      console.error('Unable to approve blueprint.', requestError)
      setBlueprintError('We could not approve this blueprint right now. Please try again.')
    } finally {
      setBlueprintSubmitting(false)
    }
  }

  const handleMaterializeBlueprint = async () => {
    if (!projectId || !blueprint || blueprint.status !== 'approved') return
    setBlueprintError(null)
    setBlueprintSubmitting(true)
    try {
      const result = await materializeBlueprint(projectId)
      setMaterialization(result)
      setProject(await getProject(projectId))
    } catch (requestError) {
      console.error('Unable to prepare project.', requestError)
      setBlueprintError('We could not prepare this project right now. Please try again.')
    } finally {
      setBlueprintSubmitting(false)
    }
  }

  const handleDatasetUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file || !projectId) return
    setDatasetError(null)
    setDatasetSubmitting(true)
    try {
      const dataset = await uploadDataset(projectId, file)
      setDatasets((current) => [dataset, ...current])
      event.target.value = ''
    } catch (requestError) {
      console.error('Unable to upload project dataset.', requestError)
      setDatasetError('We could not upload this dataset. Please try again.')
    } finally {
      setDatasetSubmitting(false)
    }
  }

  const handleDatasetDelete = async (datasetId: string) => {
    if (!projectId) return
    setDatasetError(null)
    try {
      await deleteDataset(projectId, datasetId)
      setDatasets((current) => current.filter((dataset) => dataset.id !== datasetId))
    } catch (requestError) {
      console.error('Unable to delete project dataset.', requestError)
      setDatasetError('We could not delete this dataset. Please try again.')
    }
  }

  const handleDatasetDownload = async (datasetId: string) => {
    if (!projectId) return
    setDatasetError(null)
    try {
      const { url } = await getDatasetDownloadUrl(projectId, datasetId)
      window.open(url, '_blank', 'noopener,noreferrer')
    } catch (requestError) {
      console.error('Unable to open project dataset.', requestError)
      setDatasetError('We could not open this dataset. Please try again.')
    }
  }

  const handlePublish = async () => {
    if (!projectId || !project || !blueprint || !canPublishProject(project.status, blueprint.status, project.materialized, Boolean(materialization))) return
    setError(null)
    setPublishing(true)
    try {
      setProject(await publishProject(projectId))
    } catch (requestError) {
      console.error('Unable to publish project.', requestError)
      setError('We could not publish this project right now. Please try again.')
    } finally {
      setPublishing(false)
    }
  }

  const updateField = (field: keyof ProjectInput, value: string) => {
    setForm((current) => current ? { ...current, [field]: value } : current)
  }

  const handleUpdate = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!projectId || !form) return
    setError(null)
    setSubmitting(true)
    try {
      const updatedProject = await updateProject(projectId, form)
      setProject(updatedProject)
      setForm(projectInput(updatedProject))
      setEditing(false)
    } catch (requestError) {
      console.error('Unable to update project.', requestError)
      setError('We could not save these project changes. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  const handleArchive = async () => {
    if (!projectId) return
    setError(null)
    setSubmitting(true)
    try {
      const archivedProject = await archiveProject(projectId)
      setProject(archivedProject)
      setForm(projectInput(archivedProject))
      setEditing(false)
    } catch (requestError) {
      console.error('Unable to archive project.', requestError)
      setError('We could not archive this project right now. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) return <BusinessAppShell><main className="business-shell"><div className="business-state-skeleton" aria-label="Loading project"><span /><span /><span /><span /></div></main></BusinessAppShell>
  if (error && !project) return <BusinessAppShell><main className="business-shell"><section className="business-content" aria-labelledby="project-load-error-title"><h1 id="project-load-error-title">Project unavailable</h1><p className="business-error-message" role="alert">{error}</p><Button onClick={() => { setLoading(true); setError(null); setProjectRetryCount((count) => count + 1) }}>Retry</Button></section></main></BusinessAppShell>
  if (!project || !form) return <BusinessAppShell><main className="business-shell"><section className="business-content"><h1>Project not found</h1><p className="business-muted">This project may have been removed or is unavailable to your account.</p></section></main></BusinessAppShell>

  const isPublished = project.status === 'active'
  const isMaterialized = project.materialized || Boolean(materialization)
  const canPublish = Boolean(blueprint && canPublishProject(project.status, blueprint.status, project.materialized, Boolean(materialization)))
  const publishingStatus = isPublished ? 'Published' : canPublish ? 'Ready to publish' : 'Action unavailable'

  return (
    <BusinessAppShell>
      <main className={`business-shell${blueprint ? ' business-shell-blueprint-review' : ''}`}>
      <section className="business-content" aria-labelledby="project-title">
        <Link className="business-back-link" to="/business/projects">Back to projects</Link>
        <div className="business-header">
          <div>
            <div className="auth-eyebrow">Project details</div>
            <h1 id="project-title">{project.name}</h1>
            <p className="business-muted">Created {new Date(project.created_at).toLocaleDateString()}</p>
          </div>
          <div className="project-detail-actions">
            <span className={`project-status project-status-${project.status}`}>{project.status === 'active' ? 'Published' : project.status === 'draft' ? 'Draft' : 'Archived'}</span>
            {project.status !== 'archived' && <Button variant="outline" onClick={() => setEditing((current) => !current)}>{editing ? 'Cancel edit' : 'Edit'}</Button>}
            {project.status !== 'archived' && <Button variant="destructive" onClick={() => void handleArchive()} disabled={submitting}>Archive</Button>}
          </div>
        </div>
        {error && <p className="auth-error" role="alert">{error}</p>}
        <section className="business-workflow-section" aria-labelledby="workflow-title">
          <h2 id="workflow-title">Project workflow</h2>
          <ol className="business-workflow">
            <li className="business-workflow-complete"><span>1</span><div><strong>Project information</strong><small>Ready</small></div></li>
            <li className={datasets.some((dataset) => dataset.status === 'ready') ? 'business-workflow-complete' : ''}><span>2</span><div><strong>Dataset</strong><small>{datasetsLoading ? 'Loading' : datasets.some((dataset) => dataset.status === 'ready') ? 'Ready' : 'Add data'}</small></div></li>
            <li className={blueprint ? 'business-workflow-complete' : ''}><span>3</span><div><strong>Blueprint</strong><small>{blueprintLoading ? 'Loading' : blueprint ? blueprint.status === 'approved' ? 'Approved' : 'Draft' : 'Not started'}</small></div></li>
            <li className={blueprint?.status === 'approved' ? 'business-workflow-complete' : ''}><span>4</span><div><strong>Approval</strong><small>{blueprint?.status === 'approved' ? 'Approved' : blueprint ? 'Review needed' : 'Waiting'}</small></div></li>
            <li className={isMaterialized ? 'business-workflow-complete' : ''}><span>5</span><div><strong>Preparation</strong><small>{isMaterialized ? 'Ready' : blueprint?.status === 'approved' ? 'Not ready' : 'Waiting'}</small></div></li>
            <li className={isPublished ? 'business-workflow-complete' : ''}><span>6</span><div><strong>Publishing</strong><small>{publishingStatus}</small></div></li>
          </ol>
        </section>
        <section className="project-information-section" aria-labelledby="project-information-title">
          <div className="business-section-heading">
            <div className="auth-eyebrow">Project brief</div>
            <h2 id="project-information-title">Project information</h2>
          </div>
        {editing ? (
          <form className="project-form" onSubmit={handleUpdate}>
            <label>Project name<input value={form.name} onChange={(event) => updateField('name', event.target.value)} required /></label>
            <label>Business problem<textarea value={form.business_problem} onChange={(event) => updateField('business_problem', event.target.value)} required /></label>
            <label>Work requirements<textarea value={form.work_requirements} onChange={(event) => updateField('work_requirements', event.target.value)} required /></label>
            <label>Desired outcome<textarea value={form.desired_outcome} onChange={(event) => updateField('desired_outcome', event.target.value)} required /></label>
            <Button type="submit" disabled={submitting}>{submitting ? 'Saving...' : 'Save changes'}</Button>
          </form>
        ) : (
          <dl className="project-details">
            <div><dt>Business problem</dt><dd>{project.business_problem}</dd></div>
            <div><dt>Work requirements</dt><dd>{project.work_requirements}</dd></div>
            <div><dt>Desired outcome</dt><dd>{project.desired_outcome}</dd></div>
          </dl>
        )}
        </section>
        <section className="dataset-section" aria-labelledby="datasets-title">
          <div className="dataset-header">
            <div>
              <div className="auth-eyebrow">Project files</div>
              <h2 id="datasets-title">Datasets</h2>
              <p className="business-muted">Upload a CSV to keep the project data available for later analysis.</p>
            </div>
            <label className="dataset-upload-button ui-primary-button">
              {datasetSubmitting ? 'Uploading...' : 'Upload CSV'}
              <input type="file" accept=".csv,text/csv" onChange={(event) => void handleDatasetUpload(event)} disabled={datasetSubmitting} />
            </label>
          </div>
          {datasetError && <div className="business-error-state" role="alert"><p>{datasetError}</p><Button variant="outline" onClick={() => { setDatasetsLoading(true); setDatasetError(null); setDatasetRetryCount((count) => count + 1) }}>Retry</Button></div>}
          {datasetsLoading && <div className="business-section-skeleton" aria-label="Loading datasets"><span /><span /></div>}
          {!datasetsLoading && !datasetError && datasets.length === 0 && <div className="business-section-empty"><h3>No datasets yet</h3><p>Upload a CSV when you are ready to add project data.</p></div>}
          {!datasetsLoading && !datasetError && <div className="dataset-list">
            {datasets.map((dataset) => (
              <article className="dataset-card" key={dataset.id}>
                <div>
                  <h3>{dataset.file_name}</h3>
                  <p className="business-muted">{dataset.status === 'ready' ? 'Ready' : dataset.status === 'pending' ? 'Preparing' : dataset.status === 'failed' ? 'Needs attention' : 'Archived'} · {dataset.row_count ?? 0} rows · {dataset.column_count ?? 0} columns · {dataset.file_size ? `${Math.ceil(dataset.file_size / 1024)} KB` : 'size unavailable'}</p>
                  {dataset.schema_metadata.columns && <p className="business-muted">Columns: {dataset.schema_metadata.columns.map((column) => `${column.name} (${column.inferred_type})`).join(', ')}</p>}
                </div>
                <div className="project-card-actions">
                  <Button variant="outline" onClick={() => void handleDatasetDownload(dataset.id)}>Open</Button>
                  <Button variant="destructive" onClick={() => void handleDatasetDelete(dataset.id)}>Delete</Button>
                </div>
              </article>
            ))}
          </div>}
        </section>
        <section className="blueprint-section" aria-labelledby="blueprint-title">
          <div className="blueprint-header">
            <div>
              <div className="auth-eyebrow">AI project understanding</div>
              <h2 id="blueprint-title">Project blueprint</h2>
              <p className="business-muted">SkillUp proposes a structured draft from your workplace context and dataset metadata.</p>
            </div>
            {!blueprintLoading && (!blueprint || blueprint.status === 'draft') && <Button onClick={() => void handleGenerateBlueprint()} disabled={blueprintSubmitting}>{blueprintSubmitting ? 'Generating...' : blueprint ? 'Regenerate draft' : 'Generate blueprint'}</Button>}
          </div>
          {blueprintError && <div className="business-error-state" role="alert"><p>{blueprintError}</p><Button variant="outline" onClick={() => { setBlueprintLoading(true); setBlueprintError(null); setBlueprintRetryCount((count) => count + 1) }}>Retry</Button></div>}
          {blueprintLoading && <div className="business-section-skeleton" aria-label="Loading blueprint"><span /><span /><span /></div>}
            {!blueprintLoading && !blueprint && !blueprintError && <div className="business-section-empty"><h3>No blueprint yet</h3><p>Upload a ready dataset, then generate a blueprint for review.</p></div>}
          {blueprint && (
            <BlueprintReview
              blueprint={blueprint}
              projectOutcome={project.desired_outcome}
              projectStatus={project.status}
              materialized={project.materialized || Boolean(materialization)}
              onApprove={() => void handleApproveBlueprint()}
              onMaterialize={() => void handleMaterializeBlueprint()}
              onPublish={() => void handlePublish()}
              onRevise={() => void handleReviseBlueprint()}
              editingDraft={editingBlueprint}
              draftForm={blueprintDraftForm}
              onToggleEdit={() => {
                setEditingBlueprint((current) => {
                  const next = !current
                  if (next && blueprint && blueprint.status === 'draft') {
                    setBlueprintDraftForm(blueprint.blueprint_json)
                  }
                  return next
                })
              }}
              onDraftFormChange={setBlueprintDraftForm}
              onSaveDraft={(e) => void handleSaveBlueprintDraft(e)}
              materialization={materialization}
              approving={blueprintSubmitting}
              publishing={publishing}
            />
          )}
        </section>
      </section>
      </main>
    </BusinessAppShell>
  )
}

function BlueprintDraftEditor({
  draft,
  onChange,
  onSave,
  onCancel,
  submitting,
}: {
  draft: ProjectBlueprint
  onChange: (updated: ProjectBlueprint) => void
  onSave: (e: FormEvent<HTMLFormElement>) => void
  onCancel: () => void
  submitting: boolean
}) {
  const updateField = <K extends keyof ProjectBlueprint>(key: K, value: ProjectBlueprint[K]) => {
    onChange({ ...draft, [key]: value })
  }

  const updateModule = (index: number, field: string, value: string) => {
    const newModules = [...draft.modules]
    newModules[index] = { ...newModules[index], [field]: value }
    onChange({ ...draft, modules: newModules })
  }

  const updateTask = (index: number, field: string, value: string) => {
    const newTasks = [...draft.tasks]
    newTasks[index] = { ...newTasks[index], [field]: value }
    onChange({ ...draft, tasks: newTasks })
  }

  return (
    <form className="project-form" onSubmit={onSave}>
      <label>
        Project summary
        <textarea
          value={draft.project_summary}
          onChange={(event) => updateField('project_summary', event.target.value)}
          required
        />
      </label>
      <label>
        Workplace goal
        <textarea
          value={draft.workplace_goal}
          onChange={(event) => updateField('workplace_goal', event.target.value)}
          required
        />
      </label>

      <h3>Work areas</h3>
      {draft.modules.map((module, idx) => (
        <fieldset key={idx} style={{ border: '1px solid var(--border, #333)', borderRadius: 8, padding: 12, marginBottom: 12 }}>
          <legend style={{ padding: '0 8px' }}>Work Area #{idx + 1}</legend>
          <label>
            Name
            <input
              value={module.name}
              onChange={(event) => updateModule(idx, 'name', event.target.value)}
              required
            />
          </label>
          <label>
            Description
            <textarea
              value={module.description}
              onChange={(event) => updateModule(idx, 'description', event.target.value)}
              required
            />
          </label>
          <label>
            How it will be done (rationale)
            <textarea
              value={module.rationale}
              onChange={(event) => updateModule(idx, 'rationale', event.target.value)}
              required
            />
          </label>
        </fieldset>
      ))}

      <h3>Assignments</h3>
      {draft.tasks.map((task, idx) => (
        <fieldset key={idx} style={{ border: '1px solid var(--border, #333)', borderRadius: 8, padding: 12, marginBottom: 12 }}>
          <legend style={{ padding: '0 8px' }}>Task #{idx + 1}: {task.title}</legend>
          <label>
            Title
            <input
              value={task.title}
              onChange={(event) => updateTask(idx, 'title', event.target.value)}
              required
            />
          </label>
          <label>
            Related Work Area
            <select
              value={task.related_module}
              onChange={(event) => updateTask(idx, 'related_module', event.target.value)}
              required
            >
              {draft.modules.map((m) => (
                <option key={m.name} value={m.name}>{m.name}</option>
              ))}
            </select>
          </label>
          <label>
            Workplace context
            <textarea
              value={task.workplace_context}
              onChange={(event) => updateTask(idx, 'workplace_context', event.target.value)}
              required
            />
          </label>
          <label>
            Instruction
            <textarea
              value={task.instruction}
              onChange={(event) => updateTask(idx, 'instruction', event.target.value)}
              required
            />
          </label>
          <label>
            Expected outcome
            <textarea
              value={task.expected_outcome}
              onChange={(event) => updateTask(idx, 'expected_outcome', event.target.value)}
              required
            />
          </label>
        </fieldset>
      ))}

      <div className="project-card-actions">
        <Button type="submit" disabled={submitting}>
          {submitting ? 'Saving draft...' : 'Save draft changes'}
        </Button>
        <Button type="button" variant="outline" onClick={onCancel}>
          Cancel edit
        </Button>
      </div>
    </form>
  )
}

function BlueprintReview({
  blueprint,
  projectOutcome,
  projectStatus,
  materialized,
  onApprove,
  onMaterialize,
  onPublish,
  onRevise,
  editingDraft,
  draftForm,
  onToggleEdit,
  onDraftFormChange,
  onSaveDraft,
  materialization,
  approving,
  publishing,
}: {
  blueprint: BlueprintRecord
  projectOutcome: string | null
  projectStatus: Project['status']
  materialized: boolean
  onApprove: () => void
  onMaterialize: () => void
  onPublish: () => void
  onRevise: () => void
  editingDraft: boolean
  draftForm: ProjectBlueprint | null
  onToggleEdit: () => void
  onDraftFormChange: (draft: ProjectBlueprint) => void
  onSaveDraft: (e: FormEvent<HTMLFormElement>) => void
  materialization: MaterializationResult | null
  approving: boolean
  publishing: boolean
}) {
  const content = blueprint.blueprint_json
  const assignmentGroups = content.modules.map((module, index) => ({
    module,
    index,
    tasks: content.tasks.filter((task) => task.related_module.trim().toLocaleLowerCase() === module.name.trim().toLocaleLowerCase()),
  }))
  const assignedTaskKeys = new Set(assignmentGroups.flatMap(({ tasks }) => tasks.map((task) => task.task_key)))
  const unassignedTasks = content.tasks.filter((task) => !assignedTaskKeys.has(task.task_key))
  const ordinal = (index: number) => String(index + 1).padStart(2, '0')
  return (
    <div className="blueprint-review">
      <div className="blueprint-status-row">
        <span className={`project-status project-status-${blueprint.status}`}>{blueprint.status} · version {blueprint.version}</span>
        {blueprint.status === 'draft' && <Button variant="outline" onClick={onToggleEdit} disabled={approving}>{editingDraft ? 'Cancel edit' : 'Edit draft'}</Button>}
        {blueprint.status === 'draft' && !editingDraft && <Button onClick={onApprove} disabled={approving}>{approving ? 'Approving...' : 'Approve blueprint'}</Button>}
        {blueprint.status === 'approved' && <Button variant="outline" onClick={onRevise} disabled={approving}>{approving ? 'Revising...' : 'Revise blueprint'}</Button>}
        {blueprint.status === 'approved' && !materialization && <Button onClick={onMaterialize} disabled={approving}>{approving ? 'Preparing...' : 'Prepare project'}</Button>}
        {projectStatus === 'draft' && blueprint.status === 'approved' && materialized && <Button onClick={onPublish} disabled={publishing}>{publishing ? 'Publishing...' : 'Publish project'}</Button>}
        {projectStatus === 'active' && <span className="business-muted">Published and available to learners</span>}
        {materialization && <span className="business-muted">Materialization ready · version {materialization.blueprint_version}</span>}
      </div>
      {blueprint.status === 'draft' && editingDraft && draftForm ? (
        <BlueprintDraftEditor
          draft={draftForm}
          onChange={onDraftFormChange}
          onSave={onSaveDraft}
          onCancel={onToggleEdit}
          submitting={approving}
        />
      ) : (
        <>
          <article className="blueprint-block"><h3>Project overview</h3><p>{content.project_summary}</p><h3>Business objective</h3><p>{content.workplace_goal}</p></article>
          <section className="blueprint-work-areas" aria-labelledby="proposed-work-areas-title">
            <div className="blueprint-content-heading">
              <div><div className="auth-eyebrow">Blueprint structure</div><h3 id="proposed-work-areas-title">Proposed work areas</h3></div>
              <span className="blueprint-content-count">{content.modules.length} {content.modules.length === 1 ? 'area' : 'areas'}</span>
            </div>
            <div className="work-area-grid">
              {assignmentGroups.map(({ module, tasks }, index) => {
                const resources = tasks.flatMap((task) => task.dataset_fields).filter((field, fieldIndex, fields) => fields.indexOf(field) === fieldIndex)
                const method = /\b(use|using|through|by|with|inspect|review|apply|create|build|analy[sz]e|query|filter|group|aggregate|test|validate)\b/i.test(module.rationale) ? module.rationale : tasks.map((task) => task.instruction).filter(Boolean).join(' ')
                return <article className="work-area-card" key={module.name}>
                  <span className="blueprint-card-number" aria-hidden="true">{ordinal(index)}</span>
                  <h4>{module.name}</h4>
                  <p className="work-area-description">{module.description}</p>
                  <div className="blueprint-card-detail"><h5>How it will be done</h5><p>{method || module.rationale}</p></div>
                  <div className="blueprint-card-detail blueprint-card-outcome"><h5>Expected outcome</h5><p>{module.description}</p></div>
                  {resources.length > 0 && <div className="blueprint-card-detail"><h5>Resources</h5><p className="blueprint-resource-list">{resources.map((resource) => <span key={resource}>{resource}</span>)}</p></div>}
                </article>
              })}
            </div>
          </section>
          <section className="blueprint-assignments" aria-labelledby="proposed-assignments-title">
            <div className="blueprint-content-heading">
              <div><div className="auth-eyebrow">Work to be completed</div><h3 id="proposed-assignments-title">Proposed assignments</h3></div>
              <span className="blueprint-content-count">{content.tasks.length} {content.tasks.length === 1 ? 'assignment' : 'assignments'}</span>
            </div>
            <div className="assignment-groups">
              {assignmentGroups.filter(({ tasks }) => tasks.length > 0).map(({ module, tasks, index }) => <section className="assignment-group" key={module.name} aria-labelledby={`assignment-work-area-${index}`}>
                <h4 id={`assignment-work-area-${index}`}><span>{ordinal(index)}</span>{module.name}</h4>
                <div className="assignment-grid">
                  {tasks.map((task, taskIndex) => <article className="assignment-card" key={task.task_key}>
                    <span className="blueprint-card-number" aria-hidden="true">{ordinal(taskIndex)}</span>
                    <h5>{task.title}</h5>
                    <div className="assignment-metadata"><span>{task.related_module}</span><span className={`assignment-difficulty assignment-difficulty-${task.difficulty}`}>{task.difficulty}</span></div>
                    <p>{task.workplace_context}</p>
                    <div className="blueprint-card-detail blueprint-card-outcome"><h6>Expected output</h6><p>{task.expected_outcome}</p></div>
                  </article>)}
                </div>
              </section>)}
              {unassignedTasks.length > 0 && <section className="assignment-group" aria-labelledby="assignment-work-area-unassigned">
                <h4 id="assignment-work-area-unassigned">Other assignments</h4>
                <div className="assignment-grid">
                  {unassignedTasks.map((task, taskIndex) => <article className="assignment-card" key={task.task_key}>
                    <span className="blueprint-card-number" aria-hidden="true">{ordinal(taskIndex)}</span>
                    <h5>{task.title}</h5>
                    <div className="assignment-metadata"><span>{task.related_module}</span><span className={`assignment-difficulty assignment-difficulty-${task.difficulty}`}>{task.difficulty}</span></div>
                    <p>{task.workplace_context}</p>
                    <div className="blueprint-card-detail blueprint-card-outcome"><h6>Expected output</h6><p>{task.expected_outcome}</p></div>
                  </article>)}
                </div>
              </section>}
            </div>
          </section>
          <article className="blueprint-block"><h3>Overall expected outcome</h3><p>{projectOutcome || content.workplace_goal}</p></article>
        </>
      )}
    </div>
  )
}
