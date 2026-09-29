import { getApi } from './client'

export type AdaptiveSupportLevel = 'independent' | 'moderate' | 'guided'
export type AdaptivePresentationDifficulty = 'foundational' | 'standard' | 'stretch'
export type GuidedStepLevel = 'none' | 'moderate' | 'explicit'
export type ExplanationDepth = 'concise' | 'standard' | 'detailed'

export interface AdaptiveEvidenceSummary {
  relevant_concept_ids: string[]
  relevant_competency_ids: string[]
  demonstrated_evidence_count: number
  developing_evidence_count: number
  relevant_failure_count: number
  repeated_failure_count: number
  historical_mastery_preserved: boolean
}

export interface AdaptivePresentationDecision {
  project_id: string
  target_task_id: string
  task_type: string
  task_difficulty: string
  support_level: AdaptiveSupportLevel
  presentation_difficulty: AdaptivePresentationDifficulty
  hints_available: boolean
  examples_available: boolean
  guided_step_level: GuidedStepLevel
  explanation_depth: ExplanationDepth
  reason: string
  evidence_used: AdaptiveEvidenceSummary
}

/** Retrieves the backend-owned presentation decision without changing learner state. */
export function getAdaptiveDecision(
  projectId: string,
  taskId: string,
): Promise<AdaptivePresentationDecision> {
  return getApi<AdaptivePresentationDecision>(
    `/projects/${projectId}/tasks/${taskId}/adaptive-decision`,
  )
}
