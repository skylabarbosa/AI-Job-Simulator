import { ApiError, deleteApi, getApi, postFileApi } from './client.ts'

export function formatDatasetErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    if (error.isNetworkError) {
      return 'Unable to connect to the backend server. Please verify your network connection or that the server is running.'
    }
    if (error.status === 401 || error.status === 403) {
      return 'You do not have permission to access project resources. Please check your credentials.'
    }
    if (error.status === 404) {
      return 'Project resources were not found.'
    }
    if (error.status === 409) {
      return 'Project blueprint is not approved for resource access.'
    }
    if (error.status && error.status >= 500) {
      return error.detail ? `Backend error: ${error.detail}` : 'Backend service failure. Please try again later.'
    }
    if (error.detail) {
      return error.detail
    }
    if (error.message && error.message !== 'Failed to fetch') {
      return error.message
    }
  }
  if (error instanceof Error) {
    if (error.message === 'Failed to fetch') {
      return 'Unable to connect to the backend server. Please verify the backend is running.'
    }
    return error.message
  }
  return fallback
}

export interface DatasetColumn {
  name: string
  inferred_type: string
  missing_count: number
}

export interface Dataset {
  id: string
  project_id: string
  file_name: string
  storage_path: string
  file_type: string
  file_size: number | null
  row_count: number | null
  column_count: number | null
  schema_metadata: { columns?: DatasetColumn[] }
  status: 'pending' | 'ready' | 'failed' | 'archived'
  uploaded_at: string | null
  created_at: string
  updated_at: string
}

export interface DatasetPreview {
  dataset_id: string
  file_name: string
  columns: string[]
  rows: Array<Record<string, string>>
  row_limit: number
  total_rows: number | null
}

export function listDatasets(projectId: string): Promise<Dataset[]> {
  return getApi<Dataset[]>(`/projects/${projectId}/datasets`)
}

export function uploadDataset(projectId: string, file: File): Promise<Dataset> {
  return postFileApi<Dataset>(`/projects/${projectId}/datasets`, file)
}

export function deleteDataset(projectId: string, datasetId: string): Promise<void> {
  return deleteApi(`/projects/${projectId}/datasets/${datasetId}`)
}

export function getDatasetDownloadUrl(projectId: string, datasetId: string): Promise<{ url: string }> {
  return getApi<{ url: string }>(`/projects/${projectId}/datasets/${datasetId}/download`)
}

export function getDatasetPreview(
  projectId: string,
  datasetId: string,
  limit = 10,
): Promise<DatasetPreview> {
  return getApi<DatasetPreview>(`/projects/${projectId}/datasets/${datasetId}/preview?limit=${limit}`)
}
