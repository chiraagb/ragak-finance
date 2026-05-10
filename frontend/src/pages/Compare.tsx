import { useState, useEffect } from 'react'
import { api } from '../api/client'
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  ResponsiveContainer, Legend, Tooltip,
} from 'recharts'

interface FundSearchResult { id: string; scheme_code?: number; name: string; amc_name: string; has_local_data?: boolean }
interface Profile { id: string; name: string }
interface CompareRow {
  fund_id: string; fund_name: string; total_score: number
  breakdown: Record<string, { raw_value: number | null; normalized_score: number; weight: number; weighted_contribution: number; unit: string; higher_is_better: boolean }>
}

const CHART_COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6']

export default function Compare() {
  const [query, setQuery] = useState('')
  const [searchResults, setSearchResults] = useState<FundSearchResult[]>([])
  const [selected, setSelected] = useState<FundSearchResult[]>([])
  const [profiles, setProfiles] = useState<Profile[]>([])
  const [profileId, setProfileId] = useState('')
  const [comparison, setComparison] = useState<CompareRow[]>([])
  const [loading, setLoading] = useState(false)
  const [searchLoading, setSearchLoading] = useState(false)

  useEffect(() => {
    api.get('/api/ranking/profiles').then(r => {
      setProfiles(r.data)
      if (r.data.length > 0) setProfileId(r.data[0].id)
    })
  }, [])

  useEffect(() => {
    if (query.length < 2) { setSearchResults([]); return }
    const t = setTimeout(() => {
      setSearchLoading(true)
      api.get(`/api/funds/search?q=${encodeURIComponent(query)}`)
        .then(r => setSearchResults(r.data.filter((f: FundSearchResult) => !selected.find(s => s.id === f.id))))
        .finally(() => setSearchLoading(false))
    }, 300)
    return () => clearTimeout(t)
  }, [query, selected])

  const addFund = (fund: FundSearchResult) => {
    if (selected.length >= 5 || selected.find(s => s.id === fund.id)) return
    setSelected(prev => [...prev, fund])
    setQuery('')
    setSearchResults([])
  }

  const removeFund = (id: string) => setSelected(prev => prev.filter(f => f.id !== id))

  const compare = async () => {
    if (selected.length < 2 || !profileId) return
    setLoading(true)
    try {
      const ids = selected.map(f => f.id).join(',')
      const res = await api.get(`/api/ranking/compare?fund_ids=${ids}&profile_id=${profileId}`)
      setComparison(res.data)
    } finally {
      setLoading(false)
    }
  }

  // Build radar chart data from normalized scores
  const radarData = comparison.length > 0
    ? Object.keys(comparison[0].breakdown).map(key => {
        const entry: Record<string, string | number> = { metric: key.replace(/_/g, ' ') }
        comparison.forEach(c => { entry[c.fund_name] = Math.round(c.breakdown[key]?.normalized_score * 100) })
        return entry
      })
    : []

  // All metric keys for the comparison table
  const metricKeys = comparison.length > 0 ? Object.keys(comparison[0].breakdown) : []

  return (
    <div className="max-w-6xl mx-auto">
      <h1 className="text-xl font-semibold mb-4">Fund Comparison</h1>

      {/* Fund selector */}
      <div className="bg-white rounded-xl border border-gray-200 p-4 mb-4">
        <div className="flex flex-wrap gap-2 mb-3">
          {selected.map((f, i) => (
            <span key={f.id} className="flex items-center gap-1 px-3 py-1 rounded-full text-sm font-medium text-white" style={{ backgroundColor: CHART_COLORS[i] }}>
              {f.name}
              <button onClick={() => removeFund(f.id)} className="ml-1 opacity-75 hover:opacity-100">×</button>
            </span>
          ))}
        </div>

        <div className="flex gap-2">
          <div className="relative flex-1">
            <input
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder={selected.length >= 5 ? 'Max 5 funds' : 'Search and add a fund...'}
              value={query}
              onChange={e => setQuery(e.target.value)}
              disabled={selected.length >= 5}
            />
            {searchResults.length > 0 && (
              <div className="absolute top-full left-0 right-0 bg-white border border-gray-200 rounded-lg shadow-lg mt-1 z-10">
                {searchResults.slice(0, 8).map(f => (
                  <button key={f.id} onClick={() => addFund(f)}
                    className="w-full text-left px-3 py-2 text-sm hover:bg-gray-50 border-b border-gray-100 last:border-0 flex items-center justify-between gap-2">
                    <div className="min-w-0">
                      <span className="font-medium block truncate">{f.name}</span>
                      {f.amc_name && <span className="text-gray-400 text-xs">{f.amc_name}</span>}
                    </div>
                    {f.has_local_data && (
                      <span className="text-xs bg-green-100 text-green-700 px-1.5 py-0.5 rounded shrink-0">metrics</span>
                    )}
                  </button>
                ))}
              </div>
            )}
            {searchLoading && <span className="absolute right-3 top-2 text-gray-400 text-xs">Searching...</span>}
          </div>

          <select
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none"
            value={profileId}
            onChange={e => setProfileId(e.target.value)}
          >
            {profiles.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>

          <button
            onClick={compare}
            disabled={selected.length < 2 || loading}
            className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {loading ? 'Comparing...' : 'Compare'}
          </button>
        </div>
      </div>

      {comparison.length > 0 && (
        <>
          {/* Radar chart */}
          {radarData.length > 0 && (
            <div className="bg-white rounded-xl border border-gray-200 p-4 mb-4">
              <h2 className="text-sm font-semibold text-gray-600 mb-3">Score Radar</h2>
              <ResponsiveContainer width="100%" height={300}>
                <RadarChart data={radarData}>
                  <PolarGrid />
                  <PolarAngleAxis dataKey="metric" tick={{ fontSize: 11 }} />
                  <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fontSize: 10 }} />
                  {comparison.map((c, i) => (
                    <Radar key={c.fund_id} name={c.fund_name} dataKey={c.fund_name}
                      stroke={CHART_COLORS[i]} fill={CHART_COLORS[i]} fillOpacity={0.15} />
                  ))}
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Tooltip formatter={(v: number) => `${v}`} />
                </RadarChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Score summary */}
          <div className="grid gap-3 mb-4" style={{ gridTemplateColumns: `repeat(${comparison.length}, 1fr)` }}>
            {comparison.map((c, i) => (
              <div key={c.fund_id} className="bg-white rounded-xl border-2 p-4" style={{ borderColor: CHART_COLORS[i] }}>
                <p className="text-xs text-gray-500 truncate">{c.fund_name}</p>
                <p className="text-2xl font-bold mt-1" style={{ color: CHART_COLORS[i] }}>
                  {(c.total_score * 100).toFixed(1)}
                </p>
                <p className="text-xs text-gray-400">composite score</p>
              </div>
            ))}
          </div>

          {/* Metric-by-metric table */}
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <table className="w-full text-xs">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">Metric</th>
                  {comparison.map((c, i) => (
                    <th key={c.fund_id} className="px-4 py-3 text-right font-medium" style={{ color: CHART_COLORS[i] }}>
                      {c.fund_name.split(' ').slice(0, 3).join(' ')}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {metricKeys.map(key => {
                  const values = comparison.map(c => c.breakdown[key]?.raw_value)
                  const scores = comparison.map(c => c.breakdown[key]?.normalized_score ?? 0)
                  const bestIdx = scores.indexOf(Math.max(...scores))
                  const higherIsBetter = comparison[0].breakdown[key]?.higher_is_better
                  return (
                    <tr key={key} className="border-t border-gray-100 hover:bg-gray-50">
                      <td className="px-4 py-2 text-gray-700 font-medium">{key.replace(/_/g, ' ')}</td>
                      {comparison.map((c, i) => {
                        const raw = c.breakdown[key]?.raw_value
                        const unit = c.breakdown[key]?.unit
                        return (
                          <td key={c.fund_id} className={`px-4 py-2 text-right ${i === bestIdx ? 'font-semibold text-green-700' : 'text-gray-600'}`}>
                            {raw != null ? `${raw}${unit === 'percentage' ? '%' : unit === 'days' ? 'd' : unit === 'crores' ? 'Cr' : ''}` : '—'}
                            {i === bestIdx && raw != null && <span className="ml-1 text-green-500">★</span>}
                          </td>
                        )
                      })}
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </>
      )}

      {comparison.length === 0 && selected.length >= 2 && !loading && (
        <div className="text-center text-gray-400 py-12">Select a profile and click Compare</div>
      )}
      {selected.length < 2 && (
        <div className="text-center text-gray-400 py-12">Add at least 2 funds to compare</div>
      )}
    </div>
  )
}
