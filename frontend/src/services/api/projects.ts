import { getApi, patchApi, postApi } from './client.ts'
import type { LearnerProgressResponse } from './learner'

export interface Project {
  id: string
  name: string
  slug: string
  business_problem: string | null
  work_requirements: string | null
  desired_outcome: string | null
  created_by: string | null
  status: 'draft' | 'active' | 'archived'
  materialized: boolean
  created_at: string
  updated_at: string
}

export interface ProjectInput {
  name: string
  business_problem: string
  work_requirements: string
  desired_outcome: string
}

export interface LearnerProject {
  id: string
  name: string
  slug: string
  project_summary: string
  business_objective: string
  expected_outcome: string
  work_areas: Array<{ name: string; description: string }>
}

export type LearnerProjectStatus = 'not_started' | 'in_progress' | 'completed'
export type LearnerProjectWithStatus = LearnerProject & {
  learner_status: LearnerProjectStatus
  progress: number
  completed_tasks: number
  total_tasks: number
}

export function withLearnerProgress(
  projects: LearnerProject[],
  progress: LearnerProgressResponse,
): LearnerProjectWithStatus[] {
  const progressByProject = new Map(progress.projects.map((item) => [item.project_id, item]))
  return projects.map((project) => {
    const activity = progressByProject.get(project.id)
    return {
      ...project,
      learner_status: activity?.completed
        ? 'completed'
        : (activity?.completed_tasks ?? 0) > 0 ? 'in_progress' : 'not_started',
      progress: activity?.progress ?? 0,
      completed_tasks: activity?.completed_tasks ?? 0,
      total_tasks: activity?.total_tasks ?? 0,
    }
  })
}

export function listProjects(): Promise<Project[]> {
  return getApi<Project[]>('/projects')
}

export function listAvailableProjects(): Promise<LearnerProject[]> {
  return getApi<LearnerProject[]>('/projects/available')
}

export function getProject(projectId: string): Promise<Project> {
  return getApi<Project>(`/projects/${projectId}`)
}

export function createProject(input: ProjectInput): Promise<Project> {
  return postApi<Project>('/projects', input)
}

export function updateProject(projectId: string, input: ProjectInput): Promise<Project> {
  return patchApi<Project>(`/projects/${projectId}`, input)
}

export function archiveProject(projectId: string): Promise<Project> {
  return postApi<Project>(`/projects/${projectId}/archive`)
}

export function publishProject(projectId: string): Promise<Project> {
  return postApi<Project>(`/projects/${projectId}/publish`)
}
