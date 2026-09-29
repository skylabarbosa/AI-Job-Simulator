import assert from 'node:assert/strict'
import test from 'node:test'

import { canPublishProject } from './projectPublishing.ts'

test('allows publishing when materialization was loaded from persisted project state', () => {
  assert.equal(canPublishProject('draft', 'approved', true, false), true)
})

test('does not allow publishing before approval or materialization', () => {
  assert.equal(canPublishProject('draft', 'draft', true, false), false)
  assert.equal(canPublishProject('draft', 'approved', false, false), false)
})