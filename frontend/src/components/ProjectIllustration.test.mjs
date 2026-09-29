import assert from 'node:assert/strict'
import test from 'node:test'

import { buildProjectIllustrationAltText, getProjectIllustrationSource } from './ProjectIllustrationData.ts'

test('selects the correct project artwork for known project names', () => {
  assert.equal(getProjectIllustrationSource('Toxic Analysis'), '/assets/projects/toxic-analysis.svg')
  assert.equal(getProjectIllustrationSource('Employee Performance Analysis'), '/assets/projects/employee-performance-analysis.svg')
  assert.equal(getProjectIllustrationSource('Operations Review'), '')
})

test('generates accessible alt text from the project name when no override is provided', () => {
  assert.equal(buildProjectIllustrationAltText('Toxic Analysis'), 'Toxic Analysis project illustration')
  assert.equal(buildProjectIllustrationAltText('Employee Performance Analysis', 'Custom alt'), 'Custom alt')
})
