import { getApi } from './client.ts'

export interface LearnerProgressTotals {
  projects_started: number
  completed_projects: number
  total_tasks: number
  completed_tasks: number
  average_progress: number
}

export interface LearnerRecentActivity {
  project_id?: string | null
  project_name?: string | null
  task_id?: string | null
  task_title?: string | null
  status?: string | null
  submitted_at?: string | null
  attempt_number?: number | null
  evaluation_status?: string | null
  score?: number | null
}

export interface LearnerProgressProject {
  project_id: string
  project_name?: string | null
  status?: string | null
  total_tasks: number
  completed_tasks: number
  progress: number
  completed: boolean
  started_at?: string | null
  completed_at?: string | null
}

export interface LearnerProgressResponse {
  projects: LearnerProgressProject[]
  totals: LearnerProgressTotals
  recent_activity: LearnerRecentActivity[]
}

export interface LearnerSkillTotals {
  total_skills: number
  demonstrated_skills: number
  average_score: number
}

export interface LearnerSkill {
  id: string
  name: string
  kind: 'competency' | 'concept'
  level: string
  score: number
  demonstrated: boolean
  evidence_count?: number
  source_project_ids?: string[]
  source_task_ids?: string[]
  last_evaluated_at?: string | null
}

export interface LearnerSkillsResponse {
  skills: LearnerSkill[]
  totals: LearnerSkillTotals
}

function toNumber(value: unknown, fallback = 0): number {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value
  }
  if (typeof value === 'string' && value.trim() !== '') {
    const parsed = Number(value)
    if (Number.isFinite(parsed)) {
      return parsed
    }
  }
  return fallback
}

function toBoolean(value: unknown, fallback = false): boolean {
  if (typeof value === 'boolean') {
    return value
  }
  return fallback
}

export async function getLearnerProgress(): Promise<LearnerProgressResponse> {
  const response = await getApi<Partial<LearnerProgressResponse>>('/learner/progress')
  const projects = Array.isArray(response.projects) ? response.projects : []
  const totals: Partial<LearnerProgressTotals> = response.totals ?? {}
  return {
    projects: projects.map((project) => ({
      project_id: String(project?.project_id ?? ''),
      project_name: project?.project_name ?? null,
      status: project?.status ?? null,
      total_tasks: toNumber(project?.total_tasks, 0),
      completed_tasks: toNumber(project?.completed_tasks, 0),
      progress: toNumber(project?.progress, 0),
      completed: toBoolean(project?.completed, false),
      started_at: project?.started_at ?? null,
      completed_at: project?.completed_at ?? null,
    })),
    totals: {
      projects_started: toNumber(totals.projects_started, 0),
      completed_projects: toNumber(totals.completed_projects, 0),
      total_tasks: toNumber(totals.total_tasks, 0),
      completed_tasks: toNumber(totals.completed_tasks, 0),
      average_progress: toNumber(totals.average_progress, 0),
    },
    recent_activity: Array.isArray(response.recent_activity) ? response.recent_activity : [],
  }
}

export async function getLearnerSkills(): Promise<LearnerSkillsResponse> {
  const response = await getApi<Partial<LearnerSkillsResponse>>('/learner/skills')
  const skills = Array.isArray(response.skills) ? response.skills : []
  const totals: Partial<LearnerSkillTotals> = response.totals ?? {}
  return {
    skills: skills.map((skill) => ({
      id: String(skill?.id ?? ''),
      name: String(skill?.name ?? 'Skill'),
      kind: skill?.kind === 'concept' ? 'concept' : 'competency',
      level: String(skill?.level ?? 'novice'),
      score: toNumber(skill?.score, 0),
      demonstrated: toBoolean(skill?.demonstrated, false),
      evidence_count: typeof skill?.evidence_count === 'number' && Number.isFinite(skill.evidence_count)
        ? skill.evidence_count
        : undefined,
      source_project_ids: Array.isArray(skill?.source_project_ids) ? skill.source_project_ids.map((value) => String(value)) : [],
      source_task_ids: Array.isArray(skill?.source_task_ids) ? skill.source_task_ids.map((value) => String(value)) : [],
      last_evaluated_at: skill?.last_evaluated_at ?? null,
    })),
    totals: {
      total_skills: toNumber(totals.total_skills, 0),
      demonstrated_skills: toNumber(totals.demonstrated_skills, 0),
      average_score: toNumber(totals.average_score, 0),
    },
  }
}
