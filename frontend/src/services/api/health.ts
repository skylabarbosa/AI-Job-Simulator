import { getApi } from './client'

export interface HealthResponse {
  status: string
  service: string
}

export function getHealth(): Promise<HealthResponse> {
  return getApi<HealthResponse>('/health')
}