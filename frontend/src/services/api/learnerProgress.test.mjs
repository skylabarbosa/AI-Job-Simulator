import test from 'node:test'
import assert from 'node:assert/strict'

import { getLearnerProgress, getLearnerSkills } from './learner.ts'

const originalFetch = globalThis.fetch

test('getLearnerProgress handles empty response', async () => {
  globalThis.fetch = async () => ({
    ok: true,
    json: async () => ({ projects: [], totals: { projects_started: 0 }, recent_activity: [] }),
  })

  const response = await getLearnerProgress()
  assert.deepEqual(response.projects, [])
  assert.equal(response.totals.projects_started, 0)

  globalThis.fetch = originalFetch
})

test('getLearnerProgress handles multi-project response', async () => {
  globalThis.fetch = async () => ({
    ok: true,
    json: async () => ({
      projects: [
        { project_id: 'p-1', project_name: 'Project A', progress: 40, completed_tasks: 2, total_tasks: 5, completed: false },
        { project_id: 'p-2', project_name: 'Project B', progress: 100, completed_tasks: 6, total_tasks: 6, completed: true },
      ],
      totals: { projects_started: 2, completed_projects: 1 },
      recent_activity: [{ task_id: 't-1', status: 'submitted', submitted_at: '2026-01-01T00:00:00Z' }],
    }),
  })

  const response = await getLearnerProgress()
  assert.equal(response.projects.length, 2)
  assert.equal(response.projects[1].completed, true)

  globalThis.fetch = originalFetch
})

test('getLearnerProgress propagates API failures', async () => {
  globalThis.fetch = async () => ({
    ok: false,
    status: 503,
    json: async () => ({ detail: 'Progress service unavailable' }),
  })

  try {
    await assert.rejects(getLearnerProgress(), /Progress service unavailable/)
  } finally {
    globalThis.fetch = originalFetch
  }
})

test('getLearnerSkills handles no evidence', async () => {
  globalThis.fetch = async () => ({
    ok: true,
    json: async () => ({ skills: [], totals: { total_skills: 0, demonstrated_skills: 0, average_score: 0 } }),
  })

  const response = await getLearnerSkills()
  assert.deepEqual(response.skills, [])
  assert.equal(response.totals.total_skills, 0)

  globalThis.fetch = originalFetch
})

test('getLearnerSkills handles multiple skills and optional fields', async () => {
  globalThis.fetch = async () => ({
    ok: true,
    json: async () => ({
      skills: [
        { id: 'skill-1', name: 'Data Quality', kind: 'competency', level: 'proficient', score: 86, demonstrated: true, evidence_count: 2 },
        { id: 'skill-2', name: 'Feature Engineering', kind: 'concept', level: 'developing', score: 52, demonstrated: false },
      ],
      totals: { total_skills: 2, demonstrated_skills: 1, average_score: 69 },
    }),
  })

  const response = await getLearnerSkills()
  assert.equal(response.skills.length, 2)
  assert.equal(response.skills[0].demonstrated, true)
  assert.equal(response.skills[1].score, 52)

  globalThis.fetch = originalFetch
})
