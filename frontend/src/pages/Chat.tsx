import { useState, useRef, useEffect, useCallback } from 'react'
import { ChatSocket, api } from '../api/client'

interface Message {
  role: 'user' | 'assistant'
  content: string
  intent?: string
  confidence?: string
  sources?: Array<{ fund_name: string; section_type: string; page: number }>
  streaming?: boolean
}

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [toolStatus, setToolStatus] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const socketRef = useRef<ChatSocket | null>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, toolStatus])

  // Disconnect WebSocket on unmount
  useEffect(() => {
    return () => { socketRef.current?.disconnect() }
  }, [])

  const ensureSocket = useCallback(async (sid: string) => {
    if (socketRef.current?.isOpen) return socketRef.current

    const accumulated = { value: '' }

    const socket = new ChatSocket(sid, {
      onToken: (delta) => {
        accumulated.value += delta
        const val = accumulated.value
        setMessages(prev => prev.map((m, i) =>
          i === prev.length - 1 ? { ...m, content: val } : m
        ))
      },
      onToolCall: (tool) => setToolStatus(_toolLabel(tool)),
      onDone: (done) => {
        setToolStatus(null)
        setLoading(false)
        accumulated.value = ''
        setMessages(prev => prev.map((m, i) =>
          i === prev.length - 1
            ? { ...m, streaming: false, intent: done.intent, confidence: done.confidence, sources: done.sources as Message['sources'] }
            : m
        ))
      },
      onError: (msg) => {
        setLoading(false)
        setToolStatus(null)
        setMessages(prev => prev.map((m, i) =>
          i === prev.length - 1 ? { ...m, content: msg, streaming: false } : m
        ))
      },
    })

    socket.connect()
    socketRef.current = socket

    // Wait for connection to open
    await new Promise<void>((resolve) => {
      const check = setInterval(() => {
        if (socket.isOpen) { clearInterval(check); resolve() }
      }, 50)
      setTimeout(() => { clearInterval(check); resolve() }, 3000)
    })

    return socket
  }, [])

  const sendMessage = async () => {
    if (!input.trim() || loading) return
    const userText = input.trim()
    setInput('')
    setLoading(true)
    setMessages(prev => [...prev, { role: 'user', content: userText }])
    setMessages(prev => [...prev, { role: 'assistant', content: '', streaming: true }])

    try {
      let sid = sessionId
      if (!sid) {
        const res = await api.post('/api/chat/sessions', { session_name: 'New Chat' })
        sid = res.data.session_id as string
        setSessionId(sid)
      }
      const socket = await ensureSocket(sid)
      socket.send(userText)
    } catch {
      setLoading(false)
      setMessages(prev => prev.map((m, i) =>
        i === prev.length - 1 ? { ...m, content: "Couldn't connect. Please try again.", streaming: false } : m
      ))
    }
  }

  return (
    <div className="max-w-3xl mx-auto flex flex-col h-[calc(100vh-120px)]">
      <h1 className="text-xl font-semibold mb-4 text-gray-800">Fund Intelligence Chat</h1>
      <div className="flex-1 overflow-y-auto space-y-4 pb-4">
        {messages.length === 0 && (
          <div className="text-center text-gray-400 mt-20">
            <p className="text-lg">Ask me about liquid mutual funds</p>
            <p className="text-sm mt-2">e.g. "Which liquid fund is safest for an emergency fund?"</p>
          </div>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
              msg.role === 'user' ? 'bg-blue-600 text-white' : 'bg-white border border-gray-200 text-gray-800 shadow-sm'
            }`}>
              <div className="whitespace-pre-wrap">{msg.content}{msg.streaming && <span className="animate-pulse ml-1">▍</span>}</div>
              {msg.confidence && !msg.streaming && (
                <span className={`mt-2 inline-block text-xs px-2 py-0.5 rounded-full ${
                  msg.confidence === 'high' ? 'bg-green-100 text-green-700' :
                  msg.confidence === 'medium' ? 'bg-yellow-100 text-yellow-700' :
                  'bg-red-100 text-red-700'
                }`}>
                  Confidence: {msg.confidence}
                </span>
              )}
              {msg.sources && msg.sources.length > 0 && (
                <details className="mt-2">
                  <summary className="text-xs text-gray-500 cursor-pointer">Sources ({msg.sources.length})</summary>
                  <ul className="mt-1 space-y-1">
                    {msg.sources.map((s, j) => (
                      <li key={j} className="text-xs text-gray-500">
                        {s.fund_name} — {s.section_type} (p.{s.page})
                      </li>
                    ))}
                  </ul>
                </details>
              )}
            </div>
          </div>
        ))}
        {toolStatus && (
          <div className="flex justify-start">
            <div className="text-xs text-blue-500 bg-blue-50 rounded-full px-3 py-1 animate-pulse">{toolStatus}</div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>
      <div className="flex gap-2 pt-4 border-t border-gray-200">
        <input
          className="flex-1 border border-gray-300 rounded-xl px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && !e.shiftKey && sendMessage()}
          placeholder="Ask about liquid funds..."
          disabled={loading}
        />
        <button
          onClick={sendMessage}
          disabled={loading || !input.trim()}
          className="bg-blue-600 text-white px-4 py-2 rounded-xl text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
        >
          Send
        </button>
      </div>
    </div>
  )
}

function _toolLabel(tool: string): string {
  return {
    intent_detection: '🎯 Understanding your question...',
    rag_node: '🔍 Searching factsheets...',
    ranking_node: '📊 Computing rankings...',
    comparison_node: '⚖️ Comparing funds...',
    risk_node: '🛡️ Analyzing risk...',
  }[tool] || `⚙️ ${tool}...`
}
