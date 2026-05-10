import { api } from './client'

export interface ChatSession {
  session_id: string
  session_name: string
}

export const chatApi = {
  createSession: (name: string, activeFundIds: string[] = []): Promise<ChatSession> =>
    api.post('/api/chat/sessions', {
      session_name: name,
      active_fund_ids: activeFundIds,
    }).then(r => r.data),
}
