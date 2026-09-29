import type {
  AdaptivePresentationDecision,
  ExplanationDepth,
} from '../services/api/adaptive'

export interface AdaptiveTaskMetadata {
  task_type: string
  task_expected_outcome: string | null
}

export type WorkspacePresentationMode = 'independent' | 'standard' | 'guided'

export interface WorkspacePresentation {
  mode: WorkspacePresentationMode
  isAdaptive: boolean
  showHints: boolean
  showExamples: boolean
  guidedSteps: string[]
  explanation: string | null
  helpLabel: string | null
}

export type TaskPresentationKind = 'sql' | 'cleaning' | 'analysis' | 'general'
export type TaskEditorMode = 'sql' | 'response'

export interface TaskPresentationAction {
  label: string
  description: string
  title: string
  kind: 'run' | 'check'
}

export interface TaskPresentationEditor {
  heading: string
  taskTypeLabel: string
  shellClassName: string
  ariaLabel: string
  placeholder: string
  showGutter: boolean
  spellCheck: boolean
}

export interface TaskPresentationResult {
  heading: string
  readyState: string
  emptyState: string
}

export interface TaskPresentation {
  taskType: TaskPresentationKind
  editorMode: TaskEditorMode
  editor: TaskPresentationEditor
  primaryAction: TaskPresentationAction
  results: TaskPresentationResult
}

export function taskKind(taskType: string): TaskPresentationKind {
  const normalized = (taskType ?? '').trim().toLowerCase()
  if (normalized.includes('sql') || normalized.includes('query')) return 'sql'
  if (normalized.includes('clean')) return 'cleaning'
  if (normalized.includes('analysis')) return 'analysis'
  return 'general'
}

export function getTaskPresentation(taskType: string): TaskPresentation {
  const kind = taskKind(taskType)

  if (kind === 'sql') {
    return {
      taskType: 'sql',
      editorMode: 'sql',
      editor: {
        heading: 'Write and run your SQL',
        taskTypeLabel: 'SQL',
        shellClassName: 'code-editor-shell-sql',
        ariaLabel: 'SQL query editor',
        placeholder: 'SELECT *\nFROM table_name\nLIMIT 10;',
        showGutter: true,
        spellCheck: false,
      },
      primaryAction: {
        label: 'Run Query',
        description: 'Run executes a read-only query against this task dataset.',
        title: 'Run the current SQL against the task dataset.',
        kind: 'run',
      },
      results: {
        heading: 'Results',
        readyState: 'Ready',
        emptyState: 'Write a query first.',
      },
    }
  }

  if (kind === 'cleaning') {
    return {
      taskType: 'cleaning',
      editorMode: 'response',
      editor: {
        heading: 'Write your response',
        taskTypeLabel: 'Data Cleaning',
        shellClassName: 'code-editor-shell-response',
        ariaLabel: 'Your response editor',
        placeholder: 'Describe the cleaning steps you would take, the issues you identified, and how you would validate the cleaned dataset.',
        showGutter: true,
        spellCheck: true,
      },
      primaryAction: {
        label: 'Check Response',
        description: 'Check your response before submitting it for review.',
        title: 'Check your response before submitting it for review.',
        kind: 'check',
      },
      results: {
        heading: 'Results',
        readyState: 'Ready',
        emptyState: 'Your response is ready to submit.',
      },
    }
  }

  if (kind === 'analysis') {
    return {
      taskType: 'analysis',
      editorMode: 'response',
      editor: {
        heading: 'Write your analysis',
        taskTypeLabel: 'Data Analysis',
        shellClassName: 'code-editor-shell-response',
        ariaLabel: 'Your analysis editor',
        placeholder: 'Summarize your findings, evidence, and interpretation before reaching a conclusion.',
        showGutter: true,
        spellCheck: true,
      },
      primaryAction: {
        label: 'Check Response',
        description: 'Check your response before submitting it for review.',
        title: 'Check your response before submitting it for review.',
        kind: 'check',
      },
      results: {
        heading: 'Results',
        readyState: 'Ready',
        emptyState: 'Your response is ready to submit.',
      },
    }
  }

  return {
    taskType: 'general',
    editorMode: 'response',
    editor: {
      heading: 'Write your response',
      taskTypeLabel: taskType.trim() || 'Response',
      shellClassName: 'code-editor-shell-response',
      ariaLabel: 'Your response editor',
      placeholder: 'Describe your approach, evidence, and final outcome clearly.',
      showGutter: true,
      spellCheck: true,
    },
    primaryAction: {
      label: 'Check Response',
      description: 'Check your response before submitting it for review.',
      title: 'Check your response before submitting it for review.',
      kind: 'check',
    },
    results: {
      heading: 'Results',
      readyState: 'Ready',
      emptyState: 'Your response is ready to submit.',
    },
  }
}

function guidedSteps(task: AdaptiveTaskMetadata, level: AdaptivePresentationDecision['guided_step_level']): string[] {
  if (level === 'none') return []

  const expectedOutcome = task.task_expected_outcome
    ? 'Compare your draft with the expected outcome before submitting.'
    : 'Review your draft against the task instructions before submitting.'

  const stepsByKind: Record<ReturnType<typeof taskKind>, string[]> = {
    sql: [
      'Identify the data, fields, and result the instructions ask for.',
      'Build and check a small query before adding the remaining conditions.',
      expectedOutcome,
      'Run through the query once more for filters, grouping, and result shape.',
    ],
    cleaning: [
      'Inspect the data for missing, duplicate, and inconsistent values relevant to the task.',
      'Apply one transformation at a time and keep track of what changed.',
      expectedOutcome,
      'Validate that the cleaned result is usable for the stated purpose.',
    ],
    analysis: [
      'Restate the question your analysis needs to answer.',
      'Separate the data observations from your interpretation of them.',
      expectedOutcome,
      'Check that each conclusion is supported by evidence from the work.',
    ],
    general: [
      'Identify the concrete outcome the task asks you to produce.',
      'Draft a small first pass that addresses the instructions directly.',
      expectedOutcome,
      'Review the draft for completeness before submitting your work.',
    ],
  }

  const steps = stepsByKind[taskKind(task.task_type)]
  return level === 'moderate' ? steps.slice(0, 3) : steps
}

export function hintForTask(taskType: string): string {
  switch (taskKind(taskType)) {
    case 'sql':
      return 'Work from the requested result backward: decide which fields, conditions, and grouping the result needs.'
    case 'cleaning':
      return 'Name the issue, the transformation, and the check that shows the data is ready to use.'
    case 'analysis':
      return 'Connect each finding to a specific observation before drawing a conclusion or recommendation.'
    default:
      return 'Break the instructions into the smallest verifiable pieces, then address each piece in your work.'
  }
}

export function exampleApproachForTask(taskType: string): string {
  switch (taskKind(taskType)) {
    case 'sql':
      return 'A useful approach is to validate a simple result first, then add the joins, filters, or aggregation the task requires.'
    case 'cleaning':
      return 'A useful approach is to document one representative data issue, the transformation applied, and how you verified it.'
    case 'analysis':
      return 'A useful approach is to state one evidence-backed finding, explain what it means, then repeat that pattern for the remaining findings.'
    default:
      return 'A useful approach is to make a short outline from the instructions, complete each part, then compare the finished work with the expected outcome.'
  }
}

function explanationFor(
  mode: WorkspacePresentationMode,
  depth: ExplanationDepth,
  hasReason: boolean,
): string | null {
  if (mode !== 'guided' || !hasReason) return null
  if (depth === 'concise') return 'Additional guidance is available for this task.'
  if (depth === 'standard') return 'Additional guidance is available to help you work through this task at your own pace.'
  return 'Additional guidance is available for this task. Use the steps, hints, and example approach as needed; your submission remains your own work.'
}

function helpLabelFor(
  mode: WorkspacePresentationMode,
  difficulty: AdaptivePresentationDecision['presentation_difficulty'],
): string | null {
  if (mode === 'independent') return null
  if (mode === 'guided' && difficulty === 'foundational') {
    return 'Start with the core requirements'
  }
  return mode === 'guided' ? 'Additional guidance' : 'Optional help'
}

export function resolveWorkspacePresentation(
  task: AdaptiveTaskMetadata,
  decision: AdaptivePresentationDecision | null,
): WorkspacePresentation {
  if (!decision) {
    return {
      mode: 'standard',
      isAdaptive: false,
      showHints: false,
      showExamples: false,
      guidedSteps: [],
      explanation: null,
      helpLabel: null,
    }
  }

  if (decision.support_level === 'independent') {
    return {
      mode: 'independent',
      isAdaptive: true,
      showHints: false,
      showExamples: false,
      guidedSteps: [],
      explanation: null,
      helpLabel: null,
    }
  }

  if (decision.support_level === 'guided') {
    return {
      mode: 'guided',
      isAdaptive: true,
      showHints: decision.hints_available,
      showExamples: decision.examples_available,
      guidedSteps: guidedSteps(task, decision.guided_step_level),
      explanation: explanationFor('guided', decision.explanation_depth, Boolean(decision.reason)),
      helpLabel: helpLabelFor('guided', decision.presentation_difficulty),
    }
  }

  return {
    mode: 'standard',
    isAdaptive: true,
    showHints: decision.hints_available,
    showExamples: decision.examples_available,
    guidedSteps: [],
    explanation: null,
    helpLabel: helpLabelFor('standard', decision.presentation_difficulty),
  }
}
