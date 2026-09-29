export function canPublishProject(
  projectStatus: 'draft' | 'active' | 'archived',
  blueprintStatus: 'draft' | 'approved' | 'rejected',
  materialized: boolean,
  materializationLoaded: boolean,
): boolean {
  return projectStatus === 'draft'
    && blueprintStatus === 'approved'
    && (materialized || materializationLoaded)
}