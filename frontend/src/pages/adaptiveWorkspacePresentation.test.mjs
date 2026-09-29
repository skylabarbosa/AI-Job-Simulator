import assert from 'node:assert/strict'
import test from 'node:test'

import {
  exampleApproachForTask,
  getTaskPresentation,
  hintForTask,
  resolveWorkspacePresentation,
} from './adaptiveWorkspacePresentation.ts'

const task = {
  task_type: 'Data Analysis',
  task_expected_outcome: 'An evidence-backed finding and recommendation.',
}

function decision(overrides = {}) {
  return {
    project_id: 'project-fixture',
    target_task_id: 'task-fixture',
    task_type: task.task_type,
    task_difficulty: 'intermediate',
    support_level: 'moderate',
    presentation_difficulty: 'standard',
    hints_available: true,
    examples_available: true,
    guided_step_level: 'moderate',
    explanation_depth: 'standard',
    reason: 'Backend-owned presentation rationale.',
    evidence_used: {
      relevant_concept_ids: [],
      relevant_competency_ids: [],
      demonstrated_evidence_count: 0,
      developing_evidence_count: 0,
      relevant_failure_count: 0,
      repeated_failure_count: 0,
      historical_mastery_preserved: false,
    },
    ...overrides,
  }
}

test('independent presentation keeps the workspace concise without guidance', () => {
  const presentation = resolveWorkspacePresentation(
    task,
    decision({
      support_level: 'independent',
      presentation_difficulty: 'stretch',
      hints_available: false,
      examples_available: false,
      guided_step_level: 'none',
      explanation_depth: 'concise',
    }),
  )

  assert.equal(presentation.mode, 'independent')
  assert.equal(presentation.showHints, false)
  assert.equal(presentation.showExamples, false)
  assert.deepEqual(presentation.guidedSteps, [])
})

test('moderate backend support retains the normal standard workspace presentation', () => {
  const presentation = resolveWorkspacePresentation(task, decision())

  assert.equal(presentation.mode, 'standard')
  assert.equal(presentation.isAdaptive, true)
  assert.equal(presentation.explanation, null)
  assert.equal(presentation.guidedSteps.length, 0)
  assert.equal(presentation.showHints, true)
  assert.equal(presentation.showExamples, true)
  assert.equal(presentation.helpLabel, 'Optional help')
})

test('guided presentation exposes only the support the decision allows', () => {
  const presentation = resolveWorkspacePresentation(
    task,
    decision({
      support_level: 'guided',
      presentation_difficulty: 'foundational',
      guided_step_level: 'explicit',
      explanation_depth: 'detailed',
      hints_available: true,
      examples_available: true,
    }),
  )

  assert.equal(presentation.mode, 'guided')
  assert.equal(presentation.showHints, true)
  assert.equal(presentation.showExamples, true)
  assert.equal(presentation.guidedSteps.length, 4)
  assert.match(presentation.explanation, /submission remains your own work/i)
  assert.equal(presentation.helpLabel, 'Start with the core requirements')
})

test('adaptive failures use the unchanged default presentation without inventing a decision', () => {
  const presentation = resolveWorkspacePresentation(task, null)

  assert.equal(presentation.mode, 'standard')
  assert.equal(presentation.isAdaptive, false)
  assert.equal(presentation.explanation, null)
})

test('task-type adapters provide process guidance for SQL, cleaning, analysis, and future task types', () => {
  for (const taskType of ['SQL', 'Data Cleaning', 'Data Analysis', 'Presentation']) {
    assert.ok(hintForTask(taskType).length > 0)
    assert.ok(exampleApproachForTask(taskType).length > 0)
  }
})

test('SQL task presentation uses the code editor and query action configuration', () => {
  const presentation = getTaskPresentation('SQL')

  assert.equal(presentation.taskType, 'sql')
  assert.equal(presentation.editorMode, 'sql')
  assert.equal(presentation.primaryAction.label, 'Run Query')
  assert.equal(presentation.primaryAction.description, 'Run executes a read-only query against this task dataset.')
  assert.equal(presentation.editor.shellClassName, 'code-editor-shell-sql')
})

test('data cleaning uses a response editor and a preflight check action', () => {
  const presentation = getTaskPresentation('Data Cleaning')

  assert.equal(presentation.taskType, 'cleaning')
  assert.equal(presentation.editorMode, 'response')
  assert.equal(presentation.primaryAction.label, 'Check Response')
  assert.equal(presentation.primaryAction.description, 'Check your response before submitting it for review.')
  assert.equal(presentation.editor.shellClassName, 'code-editor-shell-response')
  assert.equal(presentation.results.emptyState, 'Your response is ready to submit.')
})

test('data analysis uses a response editor and a preflight check action', () => {
  const presentation = getTaskPresentation('Data Analysis')

  assert.equal(presentation.taskType, 'analysis')
  assert.equal(presentation.editorMode, 'response')
  assert.equal(presentation.primaryAction.label, 'Check Response')
  assert.equal(presentation.primaryAction.description, 'Check your response before submitting it for review.')
  assert.equal(presentation.editor.shellClassName, 'code-editor-shell-response')
})

test('future task types fall back to a safe response presentation', () => {
  const presentation = getTaskPresentation('Future Challenge')

  assert.equal(presentation.taskType, 'general')
  assert.equal(presentation.editorMode, 'response')
  assert.equal(presentation.primaryAction.label, 'Check Response')
  assert.equal(presentation.primaryAction.description, 'Check your response before submitting it for review.')
})
