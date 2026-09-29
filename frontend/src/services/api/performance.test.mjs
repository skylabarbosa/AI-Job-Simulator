import test from 'node:test'
import assert from 'node:assert/strict'

import { setCachedSession } from '../authSession.ts'
import { getTaskEvaluation } from './performance.ts'

const originalFetch = globalThis.fetch
const originalWindow = globalThis.window
const testSession = { access_token: 'test-access-token' }
const testWindow = { setTimeout: globalThis.setTimeout, clearTimeout: globalThis.clearTimeout }

test.beforeEach(() => {
  setCachedSession(testSession)
  globalThis.window = testWindow
})

test.afterEach(() => {
  setCachedSession(null)
  globalThis.fetch = originalFetch
  if (originalWindow === undefined) delete globalThis.window
  else globalThis.window = originalWindow
})

test('getTaskEvaluation treats the explicit missing-evaluation 404 as empty state', async () => {
  globalThis.fetch = async () => ({
    ok: false,
    status: 404,
    json: async () => ({ detail: 'Evaluation not found' }),
  })

  assert.equal(await getTaskEvaluation('project-1', 'task-1'), null)
})

test('getTaskEvaluation preserves other 404 API failures', async () => {
  globalThis.fetch = async () => ({
    ok: false,
    status: 404,
    json: async () => ({ detail: 'Project not found' }),
  })

  await assert.rejects(getTaskEvaluation('project-1', 'task-1'), /Project not found/)
})
