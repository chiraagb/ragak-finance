import { api } from './client'

export interface AMCSource {
  id: string
  amc_name: string
  factsheet_url: string
  is_active: boolean
  last_fetched_at: string | null
  last_fetch_status: string | null
  last_fetch_error: string | null
  last_document_id: string | null
  created_at: string
}

export const sourcesApi = {
  list: (): Promise<AMCSource[]> =>
    api.get('/api/amc-sources').then(r => r.data),

  create: (data: { amc_name: string; factsheet_url: string }): Promise<AMCSource> =>
    api.post('/api/amc-sources', data).then(r => r.data),

  delete: (id: string): Promise<void> =>
    api.delete(`/api/amc-sources/${id}`).then(r => r.data),

  fetch: (id: string): Promise<void> =>
    api.post(`/api/amc-sources/${id}/fetch`).then(r => r.data),

  fetchAll: (): Promise<void> =>
    api.post('/api/amc-sources/fetch-all').then(r => r.data),
}
