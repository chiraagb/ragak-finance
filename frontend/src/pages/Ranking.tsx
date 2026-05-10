import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { SlidersHorizontal } from 'lucide-react'
import { useRankingProfiles, useRankingScores } from '../hooks/useRanking'

export default function Ranking() {
  const navigate = useNavigate()
  const [selectedProfile, setSelectedProfile] = useState<string>('')
  const [expanded, setExpanded] = useState<string | null>(null)

  const { data: profiles = [] } = useRankingProfiles()
  const { data: rankings = [], isLoading } = useRankingScores(selectedProfile)

  useEffect(() => {
    if (!selectedProfile && profiles.length > 0) setSelectedProfile(profiles[0].id)
  }, [profiles, selectedProfile])

  return (
    <div className="max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-semibold">Fund Rankings</h1>
        <div className="flex items-center gap-2">
          <select
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            value={selectedProfile}
            onChange={e => setSelectedProfile(e.target.value)}
          >
            {profiles.map(p => (
              <option key={p.id} value={p.id}>{p.name}{p.is_system ? ' (System)' : ''}</option>
            ))}
          </select>
          <button
            onClick={() => navigate('/ranking/profiles')}
            className="flex items-center gap-1.5 border border-gray-300 text-gray-600 px-3 py-2 rounded-lg text-sm hover:bg-gray-50 transition-colors whitespace-nowrap"
          >
            <SlidersHorizontal size={14} />
            New Profile
          </button>
        </div>
      </div>

      {isLoading ? <p className="text-gray-500 text-sm">Computing rankings...</p> : (
        <div className="space-y-2">
          {rankings.map(fund => (
            <div key={fund.fund_id} className="bg-white border border-gray-200 rounded-xl overflow-hidden">
              <button
                className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-50 transition-colors"
                onClick={() => setExpanded(expanded === fund.fund_id ? null : fund.fund_id)}
              >
                <div className="flex items-center gap-3">
                  <span className="w-8 h-8 bg-blue-100 text-blue-700 rounded-full flex items-center justify-center text-sm font-bold">
                    {fund.rank}
                  </span>
                  <button
                    onClick={e => { e.stopPropagation(); navigate(`/funds/${fund.fund_id}`) }}
                    className="font-medium text-gray-800 hover:text-blue-700 hover:underline text-left"
                  >
                    {fund.fund_name || `Fund ${fund.fund_id.slice(0, 8)}`}
                  </button>
                </div>
                <div className="flex items-center gap-3">
                  <div className="w-24 bg-gray-200 rounded-full h-2">
                    <div className="bg-blue-600 h-2 rounded-full" style={{ width: `${fund.total_score * 100}%` }} />
                  </div>
                  <span className="text-sm font-mono text-gray-600">{(fund.total_score * 100).toFixed(1)}</span>
                </div>
              </button>
              {expanded === fund.fund_id && (
                <div className="px-4 pb-4 border-t border-gray-100">
                  <table className="w-full text-xs mt-2">
                    <thead>
                      <tr className="text-gray-500">
                        <th className="text-left py-1">Metric</th>
                        <th className="text-right py-1">Raw Value</th>
                        <th className="text-right py-1">Score</th>
                        <th className="text-right py-1">Weight</th>
                        <th className="text-right py-1">Contribution</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(fund.score_breakdown || {}).map(([key, d]) => (
                        <tr key={key} className="border-t border-gray-100">
                          <td className="py-1 text-gray-700">{key}</td>
                          <td className="py-1 text-right text-gray-600">{d.raw_value != null ? `${d.raw_value}${d.unit === 'percentage' ? '%' : ''}` : '—'}</td>
                          <td className="py-1 text-right text-gray-600">{(d.normalized_score * 100).toFixed(0)}</td>
                          <td className="py-1 text-right text-gray-600">{(d.weight * 100).toFixed(0)}%</td>
                          <td className="py-1 text-right font-medium text-blue-700">{(d.weighted_contribution * 100).toFixed(1)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          ))}
          {rankings.length === 0 && !isLoading && (
            <div className="text-center text-gray-400 py-12">
              No rankings yet. Upload fund factsheets to get started.
            </div>
          )}
        </div>
      )}
    </div>
  )
}
