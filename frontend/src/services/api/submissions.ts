import { postApi } from './client'

export interface DeterministicCheck {
  name: string
  passed: boolean
  message: string
}

export interface SkillEvidence {
  competency_id: string | null
  concept_id: string | null
  evidence: string
  level: 'demonstrated' | 'developing' | 'insufficient_evidence'
}

export interface SubmissionResult {
  submission_id: string
  evaluation_id: string | null
  validation_status: 'passed' | 'failed' | 'needs_evaluation'
  checks: DeterministicCheck[]
  message: string
  strengths: string[]
  areas_for_improvement: string[]
  evidence: string[]
  skill_evidence: SkillEvidence[]
  execution_status: 'success' | 'error' | null
  columns: string[]
  rows: Array<Array<string | number | boolean | null>>
  row_count: number | null
  displayed_row_count: number | null
  truncated: boolean
  execution_time_ms: number | null
}

export function checkTaskWork(
  projectId: string,
  taskId: string,
  response: string,
  content?: Record<string, unknown>,
): Promise<SubmissionResult> {
  return postApi<SubmissionResult>(`/projects/${projectId}/tasks/${taskId}/check`, {
    response,
    content,
  })
}

export function submitTaskWork(
  projectId: string,
  taskId: string,
  response: string,
  content?: Record<string, unknown>,
): Promise<SubmissionResult> {
  return postApi<SubmissionResult>(`/projects/${projectId}/tasks/${taskId}/submit`, {
    response,
    content,
  })
}
