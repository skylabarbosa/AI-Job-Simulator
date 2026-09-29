export function getProjectIllustrationSource(projectName: string) {
  const normalizedName = projectName.toLowerCase()

  if (normalizedName.includes('employee') || normalizedName.includes('performance')) {
    return '/assets/projects/employee-performance-analysis.svg'
  }

  if (normalizedName.includes('toxic')) {
    return '/assets/projects/toxic-analysis.svg'
  }

  return ''
}

export function buildProjectIllustrationAltText(projectName: string, explicitAlt?: string) {
  return explicitAlt ?? `${projectName} project illustration`
}
