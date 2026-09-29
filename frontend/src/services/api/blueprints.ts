import { getApi, patchApi, postApi } from './client'

export interface BlueprintConcept {
  name: string
  description: string
}

export interface BlueprintCompetency {
  name: string
  description: string
  concepts: BlueprintConcept[]
}

export interface BlueprintModule {
  name: string
  description: string
  rationale: string
  competencies: BlueprintCompetency[]
}

export interface EvaluationCriterion {
  name: string
  description: string
  what_should_be_checked: string
  evaluation_type: 'deterministic' | 'qualitative'
}

export interface BlueprintTask {
  task_key: string
  title: string
  workplace_context: string
  instruction: string
  expected_outcome: string
  difficulty: 'easy' | 'medium' | 'hard'
  task_kind: 'analysis' | 'sql' | 'data_cleaning' | 'communication' | 'other'
  related_module: string
  related_competencies: string[]
  related_concepts: string[]
  dataset_fields: string[]
  sql_tables: string[]
  sql_concepts: string[]
  evaluation_criteria: EvaluationCriterion[]
}

export interface ProjectBlueprint {
  project_summary: string
  workplace_goal: string
  modules: BlueprintModule[]
  tasks: BlueprintTask[]
}

export interface BlueprintRecord {
  id: string
  project_id: string
  version: number
  status: 'draft' | 'approved' | 'rejected'
  source_dataset_ids: string[]
  blueprint_json: ProjectBlueprint
  provider: string | null
  model: string | null
  prompt_version: string | null
  generated_by: string | null
  approved_by: string | null
  created_at: string
  updated_at: string
  approved_at: string | null
}

export interface BlueprintWorkAreaView {
  name: string
  description: string
  how_it_will_be_done: string
  resources_used: string[]
  expected_outcome: string
}

export interface BlueprintAssignmentView {
  task_key: string
  title: string
  workplace_context: string
  expected_output: string
  difficulty: 'easy' | 'medium' | 'hard'
  related_work_area: string
}

export interface BlueprintOverview {
  project_id: string
  blueprint_id: string
  version: number
  status: 'approved'
  project_name: string
  project_summary: string
  business_objective: string
  work_areas: BlueprintWorkAreaView[]
  assignments: BlueprintAssignmentView[]
  overall_expected_outcome: string
}

export async function getBlueprint(projectId: string): Promise<BlueprintRecord | null> {
  try {
    return await getApi<BlueprintRecord>(`/projects/${projectId}/blueprint`)
  } catch (error) {
    if (error instanceof Error && error.message === 'Blueprint not found') return null
    throw error
  }
}

export function generateBlueprint(projectId: string, regenerate = false): Promise<BlueprintRecord> {
  const query = regenerate ? '?regenerate=true' : ''
  return postApi<BlueprintRecord>(`/projects/${projectId}/blueprint/generate${query}`)
}

export function approveBlueprint(projectId: string, blueprintId: string): Promise<BlueprintRecord> {
  return postApi<BlueprintRecord>(`/projects/${projectId}/blueprint/approve`, { blueprint_id: blueprintId })
}

export function reviseBlueprint(projectId: string, blueprintJson?: ProjectBlueprint): Promise<BlueprintRecord> {
  return postApi<BlueprintRecord>(`/projects/${projectId}/blueprint/revise`, blueprintJson ? { blueprint_json: blueprintJson } : undefined)
}

export function updateBlueprint(projectId: string, blueprintId: string, blueprintJson: ProjectBlueprint): Promise<BlueprintRecord> {
  return patchApi<BlueprintRecord>(`/projects/${projectId}/blueprint/${blueprintId}`, { blueprint_json: blueprintJson })
}

export function getBlueprintOverview(projectId: string): Promise<BlueprintOverview> {
  return getApi<BlueprintOverview>(`/projects/${projectId}/blueprint/overview`)
}

export interface MaterializationResult {
  status: 'materialized'
  blueprint_version: number
  modules_created: number
  competencies_created: number
  concepts_created: number
  tasks_created: number
  task_competencies_created: number
  task_concepts_created: number
  rubrics_created: number
}

export function materializeBlueprint(projectId: string): Promise<MaterializationResult> {
  return postApi<MaterializationResult>(`/projects/${projectId}/blueprint/materialize`)
}
