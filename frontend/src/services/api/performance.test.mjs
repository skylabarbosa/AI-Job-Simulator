import test from 'node:test'
import assert from 'node:assert/strict'

import { getTaskEvaluation } from './performance.ts'

const originalFetch = globalThis.fetch

test('getTaskEvaluation treats the explicit missing-evaluation 404 as empty state', async () => {
  globalThis.fetch = async () => ({
    ok: false,
    status: 404,
    json: async () => ({ detail: 'Evaluation not found' }),
  })

  try {
    assert.equal(await getTaskEvaluation('project-1', 'task-1'), null)
  } finally {
    globalThis.fetch = originalFetch
  }
})

test('getTaskEvaluation preserves other 404 API failures', async () => {
  globalThis.fetch = async () => ({
    ok: false,
    status: 404,
    json: async () => ({ detail: 'Project not found' }),
  })

  try {
    await assert.rejects(getTaskEvaluation('project-1', 'task-1'), /Project not found/)
  } finally {
    globalThis.fetch = originalFetch
  }
})