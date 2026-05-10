import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

export const api = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  r => r,
  err => {
    if (err.response?.status === 401) {
      localStorage.removeItem('access_token')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

export async function streamChat(
  sessionId: string,
  content: string,
  activeProfileId: string | null,
  onToken: (delta: string) => void,
  onToolCall: (tool: string) => void,
  onDone: (payload: { intent: string; confidence: string; sources: unknown[] }) => void,
) {
  const token = localStorage.getItem('access_token')
  const res = await fetch(`${BASE_URL}/api/chat/sessions/${sessionId}/messages`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ content, active_profile_id: activeProfileId }),
  })

  if (!res.body) return
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''
    let eventType = ''
    for (const line of lines) {
      if (line.startsWith('event: ')) {
        eventType = line.slice(7).trim()
      } else if (line.startsWith('data: ')) {
        const data = JSON.parse(line.slice(6))
        if (eventType === 'token') onToken(data.delta)
        if (eventType === 'tool_call') onToolCall(data.tool)
        if (eventType === 'done') onDone(data)
      }
    }
  }
}
