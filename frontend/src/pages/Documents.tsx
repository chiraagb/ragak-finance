import { useState, useRef } from 'react'
import { Upload, Plus, Trash2, RefreshCw, PlayCircle, X } from 'lucide-react'
import { useDocuments, useUploadDocument, useReprocessDocument, useDeleteDocument } from '../hooks/useDocuments'
import { useAmcSources, useCreateAmcSource, useDeleteAmcSource, useFetchAmcSource, useFetchAllAmcSources } from '../hooks/useSources'
import type { Doc } from '../api/documents'

type Tab = 'uploads' | 'sources'

export default function Documents() {
  const [tab, setTab] = useState<Tab>('uploads')
  const [newName, setNewName] = useState('')
  const [newUrl, setNewUrl] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)

  const { data: docs = [] } = useDocuments()
  const { data: sources = [] } = useAmcSources()

  const uploadMutation = useUploadDocument()
  const reprocessMutation = useReprocessDocument()
  const deleteDocMutation = useDeleteDocument()

  const createSourceMutation = useCreateAmcSource()
  const deleteSourceMutation = useDeleteAmcSource()
  const fetchSourceMutation = useFetchAmcSource()
  const fetchAllMutation = useFetchAllAmcSources()

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

  const handleAddSource = () => {
    if (!newName.trim() || !newUrl.trim()) return
    createSourceMutation.mutate(
      { amc_name: newName.trim(), factsheet_url: newUrl.trim() },
      { onSuccess: () => { setNewName(''); setNewUrl('') } },
    )
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
              disabled={uploadMutation.isPending}
              className="flex items-center gap-1.5 bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              <Upload size={14} />
              {uploadMutation.isPending ? 'Uploading...' : 'Upload PDF'}
            </button>
            <input ref={fileRef} type="file" accept=".pdf" className="hidden"
              onChange={e => e.target.files?.[0] && uploadMutation.mutate(e.target.files[0])} />
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
                            onClick={() => reprocessMutation.mutate(doc.id)}
                            className="text-xs text-blue-600 hover:underline"
                          >
                            Retry
                          </button>
                        )}
                        <button
                          onClick={() => deleteDocMutation.mutate(doc.id)}
                          className="text-red-400 hover:text-red-600 transition-colors"
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
                onKeyDown={e => e.key === 'Enter' && handleAddSource()}
              />
              <button
                onClick={handleAddSource}
                disabled={createSourceMutation.isPending || !newName.trim() || !newUrl.trim()}
                className="flex items-center gap-1.5 bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
              >
                <Plus size={14} />
                Add
              </button>
            </div>
          </div>

          <div className="flex justify-end mb-2">
            <button
              onClick={() => fetchAllMutation.mutate()}
              disabled={fetchAllMutation.isPending || sources.filter(s => s.is_active).length === 0}
              className="flex items-center gap-1.5 text-sm text-gray-600 border border-gray-300 px-3 py-1.5 rounded-lg hover:bg-gray-50 disabled:opacity-50 transition-colors"
            >
              <RefreshCw size={13} />
              {fetchAllMutation.isPending ? 'Queuing...' : `Fetch All (${sources.filter(s => s.is_active).length})`}
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
                      {source.last_fetched_at ? new Date(source.last_fetched_at).toLocaleDateString('en-IN') : '—'}
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
                          onClick={() => fetchSourceMutation.mutate(source.id)}
                          disabled={source.last_fetch_status === 'running'}
                          className="text-blue-600 hover:text-blue-800 disabled:opacity-40 transition-colors"
                          title="Fetch now"
                        >
                          <PlayCircle size={16} />
                        </button>
                        <button
                          onClick={() => deleteSourceMutation.mutate(source.id)}
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
