import { useEffect, useState, useRef } from 'react'
import { Upload, Plus, Trash2, RefreshCw, PlayCircle, X } from 'lucide-react'
import { api } from '../api/client'

interface Doc {
  id: string; filename: string; fund_id: string | null
  status: 'pending' | 'processing' | 'done' | 'failed'
  factsheet_month: string | null; page_count: number | null; uploaded_at: string
}

interface AMCSource {
  id: string; amc_name: string; factsheet_url: string; is_active: boolean
  last_fetched_at: string | null; last_fetch_status: string | null; last_fetch_error: string | null
  last_document_id: string | null; created_at: string
}

type Tab = 'uploads' | 'sources'

export default function Documents() {
  const [tab, setTab] = useState<Tab>('uploads')

  // --- uploads state ---
  const [docs, setDocs] = useState<Doc[]>([])
  const [uploading, setUploading] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  // --- AMC sources state ---
  const [sources, setSources] = useState<AMCSource[]>([])
  const [newName, setNewName] = useState('')
  const [newUrl, setNewUrl] = useState('')
  const [addingSource, setAddingSource] = useState(false)
  const [fetchingAll, setFetchingAll] = useState(false)

  const loadDocs = () => api.get('/api/documents').then(r => setDocs(r.data))
  const loadSources = () => api.get('/api/amc-sources').then(r => setSources(r.data))

  useEffect(() => { loadDocs(); loadSources() }, [])

  useEffect(() => {
    const pending = docs.some(d => d.status === 'pending' || d.status === 'processing')
    if (!pending) return
    const timer = setInterval(loadDocs, 3000)
    return () => clearInterval(timer)
  }, [docs])

  // Poll sources while any are running
  useEffect(() => {
    const running = sources.some(s => s.last_fetch_status === 'running')
    if (!running) return
    const timer = setInterval(loadSources, 4000)
    return () => clearInterval(timer)
  }, [sources])

  const reprocess = async (id: string) => {
    await api.post(`/api/documents/${id}/reprocess`)
    await loadDocs()
  }

  const deleteDoc = async (id: string) => {
    await api.delete(`/api/documents/${id}`)
    await loadDocs()
  }

  const upload = async (file: File) => {
    setUploading(true)
    const form = new FormData()
    form.append('file', file)
    form.append('document_type', 'factsheet')
    try {
      const res = await api.post('/api/documents/upload', form, { headers: { 'Content-Type': 'multipart/form-data' } })
      if (res.data.duplicate) {
        alert(`This file was already uploaded as "${res.data.filename}".`)
      }
      await loadDocs()
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  const addSource = async () => {
    if (!newName.trim() || !newUrl.trim()) return
    setAddingSource(true)
    try {
      await api.post('/api/amc-sources', { amc_name: newName.trim(), factsheet_url: newUrl.trim() })
      setNewName(''); setNewUrl('')
      await loadSources()
    } catch {
      alert('Failed to add source')
    } finally {
      setAddingSource(false)
    }
  }

  const deleteSource = async (id: string) => {
    await api.delete(`/api/amc-sources/${id}`)
    await loadSources()
  }

  const fetchSource = async (id: string) => {
    await api.post(`/api/amc-sources/${id}/fetch`)
    setSources(prev => prev.map(s => s.id === id ? { ...s, last_fetch_status: 'running' } : s))
  }

  const fetchAll = async () => {
    setFetchingAll(true)
    try {
      await api.post('/api/amc-sources/fetch-all')
      setSources(prev => prev.map(s => s.is_active ? { ...s, last_fetch_status: 'running' } : s))
    } finally {
      setFetchingAll(false)
    }
  }

  const statusBadge = (status: Doc['status']) => {
    const map: Record<Doc['status'], string> = {
      pending: 'bg-yellow-100 text-yellow-700',
      processing: 'bg-blue-100 text-blue-700',
      done: 'bg-green-100 text-green-700',
      failed: 'bg-red-100 text-red-700',
    }
    return <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${map[status]}`}>{status}</span>
  }

  const fetchStatusBadge = (status: string | null) => {
    if (!status) return <span className="text-xs text-gray-400">never</span>
    const map: Record<string, string> = {
      success: 'bg-green-100 text-green-700',
      failed: 'bg-red-100 text-red-700',
      running: 'bg-blue-100 text-blue-700',
    }
    return <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${map[status] ?? 'bg-gray-100 text-gray-600'}`}>{status}</span>
  }

  return (
    <div className="max-w-4xl mx-auto">
      {/* Tabs */}
      <div className="flex gap-1 mb-4 border-b border-gray-200">
        {(['uploads', 'sources'] as Tab[]).map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
              tab === t ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            {t === 'uploads' ? 'Uploaded Documents' : 'AMC Sources'}
          </button>
        ))}
      </div>

      {/* --- Uploads tab --- */}
      {tab === 'uploads' && (
        <div>
          <div className="flex items-center justify-between mb-3">
            <p className="text-sm text-gray-500">Manually upload a factsheet PDF to extract metrics.</p>
            <button
              onClick={() => fileRef.current?.click()}
              disabled={uploading}
              className="flex items-center gap-1.5 bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              <Upload size={14} />
              {uploading ? 'Uploading...' : 'Upload PDF'}
            </button>
            <input ref={fileRef} type="file" accept=".pdf" className="hidden"
              onChange={e => e.target.files?.[0] && upload(e.target.files[0])} />
          </div>

          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">Filename</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">Month</th>
                  <th className="px-4 py-3 text-center font-medium text-gray-600">Pages</th>
                  <th className="px-4 py-3 text-center font-medium text-gray-600">Status</th>
                  <th className="px-4 py-3 text-right font-medium text-gray-600">Uploaded</th>
                  <th className="px-4 py-3"></th>
                </tr>
              </thead>
              <tbody>
                {docs.map(doc => (
                  <tr key={doc.id} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="px-4 py-3 text-gray-800 truncate max-w-xs">{doc.filename}</td>
                    <td className="px-4 py-3 text-gray-600">{doc.factsheet_month || '—'}</td>
                    <td className="px-4 py-3 text-center text-gray-600">{doc.page_count || '—'}</td>
                    <td className="px-4 py-3 text-center">{statusBadge(doc.status)}</td>
                    <td className="px-4 py-3 text-right text-gray-500 text-xs">
                      {new Date(doc.uploaded_at).toLocaleDateString('en-IN')}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-2">
                        {(doc.status === 'failed' || doc.status === 'pending') && (
                          <button
                            onClick={() => reprocess(doc.id)}
                            className="text-xs text-blue-600 hover:underline"
                            title="Re-queue for processing"
                          >
                            Retry
                          </button>
                        )}
                        <button
                          onClick={() => deleteDoc(doc.id)}
                          className="text-red-400 hover:text-red-600 transition-colors"
                          title="Delete document"
                        >
                          <X size={15} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
                {docs.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-4 py-12 text-center text-gray-400">
                      No documents uploaded yet. Upload a fund factsheet PDF to enable AI analysis.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* --- AMC Sources tab --- */}
      {tab === 'sources' && (
        <div>
          <div className="bg-white rounded-xl border border-gray-200 p-4 mb-4">
            <p className="text-sm text-gray-500 mb-3">
              Add factsheet PDF URLs from AMC websites. The system downloads and processes them automatically
              on the 1st of each month, or you can trigger a fetch manually.
            </p>
            <div className="flex gap-2">
              <input
                className="border border-gray-300 rounded-lg px-3 py-2 text-sm flex-1 focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="AMC name (e.g. HDFC AMC)"
                value={newName}
                onChange={e => setNewName(e.target.value)}
              />
              <input
                className="border border-gray-300 rounded-lg px-3 py-2 text-sm flex-[2] focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Factsheet PDF URL"
                value={newUrl}
                onChange={e => setNewUrl(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && addSource()}
              />
              <button
                onClick={addSource}
                disabled={addingSource || !newName.trim() || !newUrl.trim()}
                className="flex items-center gap-1.5 bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
              >
                <Plus size={14} />
                Add
              </button>
            </div>
          </div>

          <div className="flex justify-end mb-2">
            <button
              onClick={fetchAll}
              disabled={fetchingAll || sources.filter(s => s.is_active).length === 0}
              className="flex items-center gap-1.5 text-sm text-gray-600 border border-gray-300 px-3 py-1.5 rounded-lg hover:bg-gray-50 disabled:opacity-50 transition-colors"
            >
              <RefreshCw size={13} />
              {fetchingAll ? 'Queuing...' : `Fetch All (${sources.filter(s => s.is_active).length})`}
            </button>
          </div>

          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">AMC</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">URL</th>
                  <th className="px-4 py-3 text-center font-medium text-gray-600">Last Fetch</th>
                  <th className="px-4 py-3 text-center font-medium text-gray-600">Status</th>
                  <th className="px-4 py-3 text-right font-medium text-gray-600">Actions</th>
                </tr>
              </thead>
              <tbody>
                {sources.map(source => (
                  <tr key={source.id} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="px-4 py-3 font-medium text-gray-800">{source.amc_name}</td>
                    <td className="px-4 py-3 max-w-xs">
                      <a
                        href={source.factsheet_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-blue-600 hover:underline text-xs truncate block"
                        title={source.factsheet_url}
                      >
                        {source.factsheet_url}
                      </a>
                    </td>
                    <td className="px-4 py-3 text-center text-gray-500 text-xs">
                      {source.last_fetched_at
                        ? new Date(source.last_fetched_at).toLocaleDateString('en-IN')
                        : '—'}
                    </td>
                    <td className="px-4 py-3 text-center">
                      {fetchStatusBadge(source.last_fetch_status)}
                      {source.last_fetch_error && (
                        <p className="text-xs text-red-500 mt-0.5 max-w-[160px] truncate" title={source.last_fetch_error}>
                          {source.last_fetch_error}
                        </p>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={() => fetchSource(source.id)}
                          disabled={source.last_fetch_status === 'running'}
                          className="text-blue-600 hover:text-blue-800 disabled:opacity-40 transition-colors"
                          title="Fetch now"
                        >
                          <PlayCircle size={16} />
                        </button>
                        <button
                          onClick={() => deleteSource(source.id)}
                          className="text-red-400 hover:text-red-600 transition-colors"
                          title="Delete"
                        >
                          <Trash2 size={15} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
                {sources.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-4 py-12 text-center text-gray-400">
                      No AMC sources configured yet. Add a factsheet URL above to get started.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
