import test from 'node:test'
import assert from 'node:assert/strict'

import { withLearnerProgress } from './projects.ts'

test('withLearnerProgress derives available, in-progress, and completed project states', () => {
  const projects = [
    { id: 'p-1', name: 'Not started', work_areas: [] },
    { id: 'p-2', name: 'In progress', work_areas: [] },
    { id: 'p-3', name: 'Completed', work_areas: [] },
  ]
  const progress = {
    projects: [
      { project_id: 'p-2', completed: false, completed_tasks: 0, total_tasks: 4, progress: 0 },
      { project_id: 'p-3', completed: true, completed_tasks: 4, total_tasks: 4, progress: 100 },
    ],
  }

  const result = withLearnerProgress(projects, progress)

  assert.deepEqual(result.map((project) => project.learner_status), ['not_started', 'not_started', 'completed'])
  assert.deepEqual(result[1], {
    ...projects[1],
    learner_status: 'not_started',
    progress: 0,
    completed_tasks: 0,
    total_tasks: 4,
  })
})