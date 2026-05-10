import { useEffect, useState, useRef, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  PieChart, Pie, Cell, Tooltip,
  BarChart, Bar, XAxis, YAxis, ResponsiveContainer, CartesianGrid,
} from 'recharts'
import { ChatSocket } from '../api/client'
import { chatApi } from '../api/chat'
import { useFund, useFundMetrics, useFundCredit, useFundMaturity, useFundHoldings, useFundSectors, useFundHoldingsHistory } from '../hooks/useFunds'
import type { Holding } from '../api/funds'

interface ChatMessage { role: 'user' | 'assistant'; content: string; streaming?: boolean }

const TABS = ['Overview', 'Performance', 'Portfolio', 'Commentary', 'Holdings Change'] as const
type Tab = typeof TABS[number]

const CREDIT_COLORS: Record<string, string> = {
  AAA: '#22c55e', 'A1+': '#16a34a', Sovereign: '#15803d',
  'AA+': '#86efac', AA: '#bbf7d0', 'AA-': '#dcfce7',
  A: '#fde68a', 'Below A': '#f87171', Others: '#d1d5db',
}
const SECTOR_COLORS = ['#3b82f6','#8b5cf6','#06b6d4','#f59e0b','#10b981','#ef4444','#f97316','#6366f1','#ec4899','#84cc16']

const PERF_METRICS = ['returns_1y', 'returns_3y']
const PERF_LABELS: Record<string, string> = { returns_1y: '1Y', returns_3y: '3Y' }

function computeDiff(current: Holding[], previous: Holding[]) {
  const added = current.filter(c => !previous.find(p => p.instrument_name === c.instrument_name))
  const removed = previous.filter(p => !current.find(c => c.instrument_name === p.instrument_name))
  const changed = current.flatMap(c => {
    const prev = previous.find(p => p.instrument_name === c.instrument_name)
    if (!prev || Math.abs((c.percentage ?? 0) - (prev.percentage ?? 0)) < 0.1) return []
    return [{ ...c, prev_pct: prev.percentage, delta: (c.percentage ?? 0) - (prev.percentage ?? 0) }]
  })
  return { added, removed, changed }
}

export default function FundDetail() {
  const { fundId } = useParams<{ fundId: string }>()
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState<Tab>('Overview')

  // Commentary chat state
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([])
  const [chatInput, setChatInput] = useState('')
  const [chatLoading, setChatLoading] = useState(false)
  const [chatSessionId, setChatSessionId] = useState<string | null>(null)
  const chatSocketRef = useRef<ChatSocket | null>(null)
  const chatBottomRef = useRef<HTMLDivElement>(null)

  const { data: fund, isLoading: loading } = useFund(fundId)
  const { data: metrics = [] } = useFundMetrics(fundId)
  const { data: credit = [] } = useFundCredit(fundId)
  const { data: maturity = [] } = useFundMaturity(fundId)
  const { data: holdings = [] } = useFundHoldings(fundId)
  const { data: sectors = [] } = useFundSectors(fundId)
  const { data: holdingsHistory = {} } = useFundHoldingsHistory(fundId)

  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [chatMessages])

  useEffect(() => {
    return () => { chatSocketRef.current?.disconnect() }
  }, [])

  const ensureChatSocket = useCallback(async (sid: string) => {
    if (chatSocketRef.current?.isOpen) return chatSocketRef.current
    const accumulated = { value: '' }
    const socket = new ChatSocket(sid, {
      onToken: (delta) => {
        accumulated.value += delta
        const val = accumulated.value
        setChatMessages(prev => prev.map((m, i) => i === prev.length - 1 ? { ...m, content: val } : m))
      },
      onToolCall: () => {},
      onDone: () => {
        setChatLoading(false)
        accumulated.value = ''
        setChatMessages(prev => prev.map((m, i) => i === prev.length - 1 ? { ...m, streaming: false } : m))
      },
      onError: (msg) => {
        setChatLoading(false)
        setChatMessages(prev => prev.map((m, i) => i === prev.length - 1 ? { ...m, content: msg, streaming: false } : m))
      },
    })
    socket.connect()
    chatSocketRef.current = socket
    await new Promise<void>((resolve) => {
      const check = setInterval(() => { if (socket.isOpen) { clearInterval(check); resolve() } }, 50)
      setTimeout(() => { clearInterval(check); resolve() }, 3000)
    })
    return socket
  }, [])

  const sendChatMessage = async () => {
    if (!chatInput.trim() || chatLoading || !fundId) return
    const text = chatInput.trim()
    setChatInput('')
    setChatLoading(true)
    setChatMessages(prev => [...prev, { role: 'user', content: text }, { role: 'assistant', content: '', streaming: true }])
    try {
      let sid = chatSessionId
      if (!sid) {
        const session = await chatApi.createSession(`Commentary: ${fund?.name ?? fundId}`, [fundId])
        sid = session.session_id
        setChatSessionId(sid)
      }
      const socket = await ensureChatSocket(sid)
      socket.send(text)
    } catch {
      setChatLoading(false)
      setChatMessages(prev => prev.map((m, i) => i === prev.length - 1 ? { ...m, content: "Couldn't connect. Please try again.", streaming: false } : m))
    }
  }

  if (loading) return <div className="text-gray-500 text-sm p-8">Loading fund data...</div>
  if (!fund) return <div className="text-gray-500 text-sm p-8">Fund not found.</div>

  const creditData = credit.slice(0, 8).map(r => ({ name: r.rating, value: r.percentage }))
  const maturityData = maturity.map(r => ({ name: r.bucket, value: r.percentage }))
  const sectorData = sectors.slice(0, 10).map(r => ({ name: r.sector, value: r.percentage }))
  const perfMetrics = metrics.filter(m => PERF_METRICS.includes(m.key))
  const perfData = perfMetrics.map(m => ({ name: PERF_LABELS[m.key] ?? m.key, value: m.value ?? 0 }))
  const keyMetrics = metrics.filter(m => ['aaa_pct', 'expense_ratio', 'aum_crores', 'wam_days', 'lt7d_bucket_pct'].includes(m.key))

  const historyDates = Object.keys(holdingsHistory).sort().reverse()
  const diff = historyDates.length >= 2
    ? computeDiff(holdingsHistory[historyDates[0]], holdingsHistory[historyDates[1]])
    : null

  return (
    <div className="max-w-5xl mx-auto">
      <button onClick={() => navigate(-1)} className="text-sm text-blue-600 hover:underline mb-4 block">
        ← Back
      </button>

      {/* Header */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 mb-4">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-xl font-bold text-gray-900">{fund.name}</h1>
            <p className="text-sm text-gray-500 mt-1">{fund.amc_name}{fund.isin ? ` · ${fund.isin}` : ''}</p>
          </div>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-5">
          {[
            { label: 'NAV', value: fund.nav ? `₹${fund.nav.toFixed(4)}` : '—', sub: fund.nav_date ? `as of ${fund.nav_date}` : '' },
            { label: 'AUM', value: fund.aum_crores ? `₹${fund.aum_crores.toLocaleString('en-IN')} Cr` : '—', sub: '' },
            { label: 'Expense Ratio', value: fund.expense_ratio ? `${(fund.expense_ratio * 100).toFixed(2)}%` : '—', sub: '' },
            { label: 'Fund Manager', value: fund.fund_manager || '—', sub: fund.inception_date ? `Since ${fund.inception_date}` : '' },
          ].map(item => (
            <div key={item.label} className="bg-gray-50 rounded-lg p-3">
              <p className="text-xs text-gray-500">{item.label}</p>
              <p className="text-sm font-semibold text-gray-800 mt-1 truncate">{item.value}</p>
              {item.sub && <p className="text-xs text-gray-400 mt-0.5">{item.sub}</p>}
            </div>
          ))}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-4 border-b border-gray-200">
        {TABS.map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 text-sm font-medium rounded-t-lg transition-colors ${
              activeTab === tab
                ? 'bg-white border border-b-white border-gray-200 text-blue-600 -mb-px'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Tab: Overview */}
      {activeTab === 'Overview' && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {creditData.length > 0 && (
              <div className="bg-white rounded-xl border border-gray-200 p-4">
                <h2 className="text-sm font-semibold text-gray-700 mb-3">Credit Quality</h2>
                <ResponsiveContainer width="100%" height={200}>
                  <PieChart>
                    <Pie data={creditData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={75} label={({ name, value }) => `${name} ${value?.toFixed(1)}%`} labelLine={false}>
                      {creditData.map(entry => (
                        <Cell key={entry.name} fill={CREDIT_COLORS[entry.name] || '#d1d5db'} />
                      ))}
                    </Pie>
                    <Tooltip formatter={(v: number) => `${v.toFixed(1)}%`} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            )}
            {maturityData.length > 0 && (
              <div className="bg-white rounded-xl border border-gray-200 p-4">
                <h2 className="text-sm font-semibold text-gray-700 mb-3">Maturity Profile</h2>
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={maturityData} layout="vertical">
                    <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                    <XAxis type="number" domain={[0, 100]} tickFormatter={v => `${v}%`} tick={{ fontSize: 10 }} />
                    <YAxis type="category" dataKey="name" width={90} tick={{ fontSize: 10 }} />
                    <Tooltip formatter={(v: number) => `${v.toFixed(1)}%`} />
                    <Bar dataKey="value" fill="#3b82f6" radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
          {keyMetrics.length > 0 && (
            <div className="bg-white rounded-xl border border-gray-200 p-4">
              <h2 className="text-sm font-semibold text-gray-700 mb-3">Key Metrics</h2>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                {keyMetrics.map(m => (
                  <div key={m.key} className="bg-gray-50 rounded-lg p-3">
                    <p className="text-xs text-gray-500">{m.display_name}</p>
                    <p className="text-base font-semibold text-gray-800 mt-1">
                      {m.value != null ? `${m.value}${m.unit === 'percentage' ? '%' : m.unit === 'days' ? ' days' : m.unit === 'crores' ? ' Cr' : ''}` : '—'}
                    </p>
                    <p className="text-xs text-gray-400 mt-0.5">as of {m.extraction_date}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <h2 className="text-sm font-semibold text-gray-700 mb-3">Fund Details</h2>
            <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
              {[
                ['Benchmark', fund.benchmark_index],
                ['Exit Load', fund.exit_load],
                ['Inception Date', fund.inception_date],
              ].filter(([, v]) => v).map(([label, value]) => (
                <div key={label as string} className="flex flex-col">
                  <dt className="text-xs text-gray-400">{label}</dt>
                  <dd className="text-gray-700 font-medium">{value}</dd>
                </div>
              ))}
            </dl>
          </div>
        </div>
      )}

      {/* Tab: Performance */}
      {activeTab === 'Performance' && (
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <h2 className="text-sm font-semibold text-gray-700 mb-4">Returns</h2>
          {perfData.length > 0 ? (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={perfData} barSize={48}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="name" tick={{ fontSize: 13 }} />
                <YAxis tickFormatter={v => `${v}%`} tick={{ fontSize: 11 }} />
                <Tooltip formatter={(v: number) => `${v.toFixed(2)}%`} />
                <Bar dataKey="value" fill="#3b82f6" radius={[4, 4, 0, 0]}
                  label={{ position: 'top', formatter: (v: number) => `${v.toFixed(1)}%`, fontSize: 12 }} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-sm text-gray-400 py-8 text-center">No performance data available. Upload a factsheet to see returns.</p>
          )}
        </div>
      )}

      {/* Tab: Portfolio */}
      {activeTab === 'Portfolio' && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {sectorData.length > 0 && (
              <div className="bg-white rounded-xl border border-gray-200 p-4">
                <h2 className="text-sm font-semibold text-gray-700 mb-3">Sector Allocation</h2>
                <ResponsiveContainer width="100%" height={220}>
                  <PieChart>
                    <Pie data={sectorData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label={({ name, value }) => `${name.split(' ')[0]} ${value?.toFixed(1)}%`} labelLine={false}>
                      {sectorData.map((_, i) => (
                        <Cell key={i} fill={SECTOR_COLORS[i % SECTOR_COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip formatter={(v: number) => `${v.toFixed(1)}%`} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
          {holdings.length > 0 && (
            <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              <div className="px-4 py-3 border-b border-gray-100">
                <h2 className="text-sm font-semibold text-gray-700">Top Holdings</h2>
              </div>
              <table className="w-full text-xs">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-2 text-left font-medium text-gray-500">Instrument</th>
                    <th className="px-4 py-2 text-left font-medium text-gray-500">Type</th>
                    <th className="px-4 py-2 text-left font-medium text-gray-500">Rating</th>
                    <th className="px-4 py-2 text-right font-medium text-gray-500">% Portfolio</th>
                  </tr>
                </thead>
                <tbody>
                  {holdings.map((h, i) => (
                    <tr key={i} className="border-t border-gray-100 hover:bg-gray-50">
                      <td className="px-4 py-2 text-gray-800">{h.instrument_name || h.issuer || '—'}</td>
                      <td className="px-4 py-2 text-gray-500">{h.type || '—'}</td>
                      <td className="px-4 py-2">
                        {h.rating && (
                          <span className="px-2 py-0.5 rounded-full text-xs font-medium"
                            style={{ backgroundColor: `${CREDIT_COLORS[h.rating] || '#d1d5db'}30`, color: CREDIT_COLORS[h.rating] || '#374151' }}>
                            {h.rating}
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-2 text-right font-mono text-gray-600">
                        {h.percentage != null ? `${h.percentage.toFixed(2)}%` : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {holdings.length === 0 && sectorData.length === 0 && (
            <p className="text-sm text-gray-400 py-8 text-center">No portfolio data available. Upload a factsheet to see holdings.</p>
          )}
        </div>
      )}

      {/* Tab: Commentary (inline RAG chat) */}
      {activeTab === 'Commentary' && (
        <div className="bg-white rounded-xl border border-gray-200 flex flex-col" style={{ height: '480px' }}>
          <div className="px-4 py-3 border-b border-gray-100">
            <h2 className="text-sm font-semibold text-gray-700">Fund Commentary Chat</h2>
            <p className="text-xs text-gray-400 mt-0.5">Ask questions about this fund's strategy, outlook, and portfolio commentary</p>
          </div>
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {chatMessages.length === 0 && (
              <div className="text-center text-gray-400 mt-8 text-sm">
                <p>Ask about this fund's investment strategy or manager commentary</p>
                <p className="text-xs mt-1">e.g. "What is the fund manager's outlook?" or "Why is this fund positioned conservatively?"</p>
              </div>
            )}
            {chatMessages.map((msg, i) => (
              <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[85%] rounded-2xl px-3 py-2 text-sm leading-relaxed ${
                  msg.role === 'user' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-800'
                }`}>
                  <div className="whitespace-pre-wrap">{msg.content}{msg.streaming && <span className="animate-pulse ml-1">▍</span>}</div>
                </div>
              </div>
            ))}
            <div ref={chatBottomRef} />
          </div>
          <div className="flex gap-2 p-3 border-t border-gray-100">
            <input
              className="flex-1 border border-gray-300 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              value={chatInput}
              onChange={e => setChatInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && !e.shiftKey && sendChatMessage()}
              placeholder="Ask about this fund's commentary..."
              disabled={chatLoading}
            />
            <button
              onClick={sendChatMessage}
              disabled={chatLoading || !chatInput.trim()}
              className="bg-blue-600 text-white px-4 py-2 rounded-xl text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              Ask
            </button>
          </div>
        </div>
      )}

      {/* Tab: Holdings Change */}
      {activeTab === 'Holdings Change' && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-gray-700">Month-over-Month Holdings Change</h2>
            {historyDates.length >= 2 && (
              <span className="text-xs text-gray-400">{historyDates[1]} → {historyDates[0]}</span>
            )}
          </div>
          {!diff && (
            <p className="text-sm text-gray-400 py-8 text-center px-4">
              {historyDates.length === 0
                ? 'No holdings history available. Upload factsheets for multiple months to see changes.'
                : 'Need at least 2 months of data to show changes.'}
            </p>
          )}
          {diff && (
            <table className="w-full text-xs">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-2 text-left font-medium text-gray-500">Instrument</th>
                  <th className="px-4 py-2 text-left font-medium text-gray-500">Change</th>
                  <th className="px-4 py-2 text-right font-medium text-gray-500">Weight</th>
                </tr>
              </thead>
              <tbody>
                {diff.added.map((h, i) => (
                  <tr key={`add-${i}`} className="border-t border-gray-100 bg-green-50">
                    <td className="px-4 py-2 text-gray-800">{h.instrument_name || '—'}</td>
                    <td className="px-4 py-2"><span className="text-green-700 font-medium">+ Added</span></td>
                    <td className="px-4 py-2 text-right font-mono text-green-700">{h.percentage?.toFixed(2)}%</td>
                  </tr>
                ))}
                {diff.removed.map((h, i) => (
                  <tr key={`rem-${i}`} className="border-t border-gray-100 bg-red-50">
                    <td className="px-4 py-2 text-gray-800">{h.instrument_name || '—'}</td>
                    <td className="px-4 py-2"><span className="text-red-700 font-medium">− Removed</span></td>
                    <td className="px-4 py-2 text-right font-mono text-red-700">{h.percentage?.toFixed(2)}%</td>
                  </tr>
                ))}
                {diff.changed.map((h, i) => (
                  <tr key={`chg-${i}`} className="border-t border-gray-100 bg-yellow-50">
                    <td className="px-4 py-2 text-gray-800">{h.instrument_name || '—'}</td>
                    <td className="px-4 py-2">
                      <span className={`font-medium ${h.delta > 0 ? 'text-green-700' : 'text-red-700'}`}>
                        {h.delta > 0 ? '↑' : '↓'} {h.prev_pct?.toFixed(2)}% → {h.percentage?.toFixed(2)}%
                      </span>
                    </td>
                    <td className="px-4 py-2 text-right font-mono text-gray-600">{h.percentage?.toFixed(2)}%</td>
                  </tr>
                ))}
                {diff.added.length === 0 && diff.removed.length === 0 && diff.changed.length === 0 && (
                  <tr>
                    <td colSpan={3} className="px-4 py-8 text-center text-sm text-gray-400">No significant changes between these two months.</td>
                  </tr>
                )}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  )
}
