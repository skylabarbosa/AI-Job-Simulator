import { useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { Button, ButtonLink } from '../components/ui/button'
import { BusinessAppShell } from '../components/BusinessAppShell'
import { uploadDataset } from '../services/api/datasets'
import { createProject, type ProjectInput } from '../services/api/projects'

const emptyProject: ProjectInput = {
  name: '',
  business_problem: '',
  work_requirements: '',
  desired_outcome: '',
}

const projectDraftStorageKey = 'ai-job-simulator:new-project:draft:v1'

function readProjectDraft(): ProjectInput {
  try {
    const savedDraft = localStorage.getItem(projectDraftStorageKey)
    if (!savedDraft) return emptyProject

    const parsed: unknown = JSON.parse(savedDraft)
    if (typeof parsed !== 'object' || parsed === null) return emptyProject

    const draft = parsed as Record<string, unknown>
    const fields: (keyof ProjectInput)[] = [
      'name',
      'business_problem',
      'work_requirements',
      'desired_outcome',
    ]
    if (fields.some((field) => typeof draft[field] !== 'string')) return emptyProject

    return {
      name: draft.name as string,
      business_problem: draft.business_problem as string,
      work_requirements: draft.work_requirements as string,
      desired_outcome: draft.desired_outcome as string,
    }
  } catch {
    return emptyProject
  }
}

export function NewProjectPage() {
  const navigate = useNavigate()
  const [form, setForm] = useState(readProjectDraft)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [datasetFile, setDatasetFile] = useState<File | null>(null)
  const [createdProjectId, setCreatedProjectId] = useState<string | null>(null)
  const [draftSaved, setDraftSaved] = useState(false)

  useEffect(() => {
    if (createdProjectId) {
      try {
        localStorage.removeItem(projectDraftStorageKey)
      } catch {
        // Storage may be unavailable in restricted browser contexts.
      }
      return
    }

    const timeout = window.setTimeout(() => {
      try {
        const hasDraft = Object.values(form).some((value) => value.trim().length > 0)
        if (hasDraft) {
          localStorage.setItem(projectDraftStorageKey, JSON.stringify(form))
        } else {
          localStorage.removeItem(projectDraftStorageKey)
        }
        setDraftSaved(hasDraft)
      } catch {
        setDraftSaved(false)
      }
    }, 400)

    return () => window.clearTimeout(timeout)
  }, [form, createdProjectId])

  const updateField = (field: keyof ProjectInput, value: string) => {
    setForm((current) => ({ ...current, [field]: value }))
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    let projectId = createdProjectId
    try {
      if (!projectId) {
        const project = await createProject(form)
        projectId = project.id
        setCreatedProjectId(project.id)
        try {
          localStorage.removeItem(projectDraftStorageKey)
        } catch {
          // Storage may be unavailable in restricted browser contexts.
        }
        setDraftSaved(false)
      }
      if (datasetFile) await uploadDataset(projectId, datasetFile)
      navigate(`/business/projects/${projectId}`)
    } catch (requestError) {
      console.error(projectId ? 'Project created but dataset upload failed.' : 'Unable to create project.', requestError)
      setError(projectId
        ? 'Your project was created, but the dataset could not be uploaded. Retry the upload or continue to the project.'
        : 'We could not create this project right now. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <BusinessAppShell>
      <main className="business-shell">
      <section className="business-content business-form-panel" aria-labelledby="new-project-title">
        <Link className="business-back-link" to="/business/projects">Back to projects</Link>
        <div className="auth-eyebrow">Business workspace</div>
        <h1 id="new-project-title">New Project</h1>
        <p className="auth-lede">Start with the workplace challenge and the outcome your team wants to achieve.</p>
        <form className="project-form" onSubmit={handleSubmit}>
          <fieldset className="project-form-group">
            <legend>Workplace context</legend>
            <label>Project name<input value={form.name} onChange={(event) => updateField('name', event.target.value)} required disabled={Boolean(createdProjectId)} /></label>
            <p className="business-field-help">Choose a clear name your team and learners will recognize.</p>
            <label>Business problem<textarea value={form.business_problem} onChange={(event) => updateField('business_problem', event.target.value)} required disabled={Boolean(createdProjectId)} /></label>
            <p className="business-field-help">Describe the real challenge this project should address.</p>
            <label>Work requirements<textarea value={form.work_requirements} onChange={(event) => updateField('work_requirements', event.target.value)} required disabled={Boolean(createdProjectId)} /></label>
            <p className="business-field-help">Include the kind of work or decisions involved.</p>
            <label>Desired outcome<textarea value={form.desired_outcome} onChange={(event) => updateField('desired_outcome', event.target.value)} required disabled={Boolean(createdProjectId)} /></label>
            <p className="business-field-help">Explain what a useful result would look like.</p>
          </fieldset>
          <fieldset className="project-form-group">
            <legend>Project data</legend>
            <label>
              Optional dataset (CSV)
              <input
                type="file"
                accept=".csv,text/csv"
                aria-describedby="project-dataset-help"
                onChange={(event) => {
                  setDatasetFile(event.target.files?.[0] ?? null)
                  setError(null)
                }}
                disabled={submitting}
              />
              <span id="project-dataset-help" className="business-muted" aria-live="polite">
                {datasetFile ? `Selected: ${datasetFile.name}` : 'Add a CSV now or upload one later from the project page.'}
              </span>
            </label>
          </fieldset>
          <div className="project-form-actions" aria-live="polite">
            <span className="draft-saved-indicator" role="status">{draftSaved ? 'Draft saved' : ''}</span>
            <Button
              type="button"
              variant="ghost"
              size="xs"
              onClick={() => {
                try {
                  localStorage.removeItem(projectDraftStorageKey)
                } catch {
                  // Storage may be unavailable in restricted browser contexts.
                }
                setForm(emptyProject)
                setDraftSaved(false)
              }}
              disabled={Boolean(createdProjectId)}
            >
              Clear draft
            </Button>
          </div>
            {error && <p className="business-error-message" role="alert">{error}</p>}
          <div className="project-form-actions">
            <Button type="submit" disabled={submitting}>
              {submitting ? (createdProjectId ? 'Uploading dataset...' : 'Creating project...') : (createdProjectId ? 'Retry upload' : 'Create project')}
            </Button>
            {createdProjectId && <Button type="button" variant="outline" onClick={() => navigate(`/business/projects/${createdProjectId}`)}>Continue to project</Button>}
            <ButtonLink variant="outline" to="/business/projects">Cancel</ButtonLink>
          </div>
        </form>
      </section>
      </main>
    </BusinessAppShell>
  )
}
