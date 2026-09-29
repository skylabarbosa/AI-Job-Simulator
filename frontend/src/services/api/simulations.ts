import { postApi } from './client'

export interface SimulationContext {
  simulation_id: string
  project_id: string
  project_name: string
  task_id: string
  task_title: string
  task_description: string | null
  task_instructions: string | null
  task_expected_outcome: string | null
  task_type: string
  task_difficulty: string
  module_id: string
  module_name: string
  status: 'active' | 'paused' | 'completed' | 'abandoned'
  started_at: string
  activity_state: 'started' | 'resumed'
}

/**
 * Start or resume a simulation for a given project task.
 * The backend derives the learner identity from the auth token.
 * This function must never pass a learner_id in the body.
 */
export function startTask(projectId: string, taskId: string): Promise<SimulationContext> {
  return postApi<SimulationContext>(`/projects/${projectId}/tasks/${taskId}/start`)
}
