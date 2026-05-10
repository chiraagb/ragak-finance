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

type ChatHandlers = {
  onToken: (delta: string) => void
  onToolCall: (tool: string) => void
  onDone: (payload: { intent: string; confidence: string; sources: unknown[] }) => void
  onError?: (msg: string) => void
}

export class ChatSocket {
  private ws: WebSocket | null = null
  private sessionId: string
  private handlers: ChatHandlers

  constructor(sessionId: string, handlers: ChatHandlers) {
    this.sessionId = sessionId
    this.handlers = handlers
  }

  connect() {
    const token = localStorage.getItem('access_token')
    const wsBase = BASE_URL.replace(/^http/, 'ws')
    this.ws = new WebSocket(`${wsBase}/api/chat/sessions/${this.sessionId}/ws?token=${token}`)

    this.ws.onmessage = (event) => {
      const msg = JSON.parse(event.data)
      if (msg.type === 'token') this.handlers.onToken(msg.delta)
      else if (msg.type === 'tool_call') this.handlers.onToolCall(msg.tool)
      else if (msg.type === 'done') this.handlers.onDone(msg)
      else if (msg.type === 'error') this.handlers.onError?.(msg.message)
    }

    this.ws.onerror = () => this.handlers.onError?.('Connection error. Please try again.')
  }

  send(content: string, activeProfileId: string | null = null) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ content, active_profile_id: activeProfileId }))
    }
  }

  disconnect() {
    this.ws?.close()
    this.ws = null
  }

  get isOpen() {
    return this.ws?.readyState === WebSocket.OPEN
  }
}
