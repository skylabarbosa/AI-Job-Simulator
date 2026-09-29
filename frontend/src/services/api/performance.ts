import { ApiError, getApi } from './client.ts'

export interface TaskProgress {
  task_id: string
  title: string
  completed: boolean
  attempts: number
  latest_evaluation_status: string | null
  latest_score: number | null
}

export interface SkillProgress {
  id: string
  name: string
  kind: string
  level: string
  score: number
  demonstrated: boolean
}

export interface ProjectPerformance {
  project_id: string
  total_tasks: number
  completed_tasks: number
  progress: number
  completed: boolean
  tasks: TaskProgress[]
  competencies: SkillProgress[]
  concepts: SkillProgress[]
}

export function getProjectPerformance(projectId: string): Promise<ProjectPerformance> {
  return getApi<ProjectPerformance>(`/projects/${projectId}/performance`)
}

export interface TaskEvaluation {
  submission_id: string
  evaluation_type: 'deterministic' | 'ai'
  status: 'pending' | 'completed' | 'failed'
  score: number | null
  feedback: string | null
  evaluated_at: string | null
  strengths: string[]
  areas_for_improvement: string[]
  evidence: string[]
}

export function getTaskEvaluation(projectId: string, taskId: string): Promise<TaskEvaluation | null> {
  return getApi<TaskEvaluation>(`/projects/${projectId}/tasks/${taskId}/evaluation`).catch((error: unknown) => {
    if (error instanceof ApiError && error.status === 404 && error.detail === 'Evaluation not found') {
      return null
    }
    throw error
  })
}
