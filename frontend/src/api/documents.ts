import { api } from './client'

export interface Doc {
  id: string
  filename: string
  fund_id: string | null
  status: 'pending' | 'processing' | 'done' | 'failed'
  factsheet_month: string | null
  page_count: number | null
  uploaded_at: string
}

export const documentsApi = {
  list: (): Promise<Doc[]> =>
    api.get('/api/documents').then(r => r.data),

  upload: (file: File): Promise<{ duplicate?: boolean; filename?: string; id: string }> => {
    const form = new FormData()
    form.append('file', file)
    form.append('document_type', 'factsheet')
    return api.post('/api/documents/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then(r => r.data)
  },

  reprocess: (id: string): Promise<void> =>
    api.post(`/api/documents/${id}/reprocess`).then(r => r.data),

  delete: (id: string): Promise<void> =>
    api.delete(`/api/documents/${id}`).then(r => r.data),
}
