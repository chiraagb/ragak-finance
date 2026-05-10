import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  PieChart, Pie, Cell, Tooltip, Legend,
  BarChart, Bar, XAxis, YAxis, ResponsiveContainer, CartesianGrid,
} from 'recharts'
import { api } from '../api/client'

interface FundInfo {
  id: string; name: string; amc_name: string; isin: string | null
  nav: number | null; nav_date: string | null; aum_crores: number | null
  expense_ratio: number | null; fund_manager: string | null
  inception_date: string | null; benchmark_index: string | null; exit_load: string | null
}
interface Metric { key: string; display_name: string; value: number | null; unit: string; extraction_date: string }
interface CreditRow { rating: string; percentage: number }
interface MaturityRow { bucket: string; percentage: number }
interface Holding { name: string | null; issuer: string | null; rating: string | null; pct: number | null; type: string | null }

const CREDIT_COLORS: Record<string, string> = {
  AAA: '#22c55e', 'A1+': '#16a34a', Sovereign: '#15803d',
  'AA+': '#86efac', AA: '#bbf7d0', 'AA-': '#dcfce7',
  A: '#fde68a', 'Below A': '#f87171', Others: '#d1d5db',
}

export default function FundDetail() {
  const { fundId } = useParams<{ fundId: string }>()
  const navigate = useNavigate()
  const [fund, setFund] = useState<FundInfo | null>(null)
  const [metrics, setMetrics] = useState<Metric[]>([])
  const [credit, setCredit] = useState<CreditRow[]>([])
  const [maturity, setMaturity] = useState<MaturityRow[]>([])
  const [holdings, setHoldings] = useState<Holding[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!fundId) return
    setLoading(true)
    Promise.all([
      api.get(`/api/funds/${fundId}`),
      api.get(`/api/funds/${fundId}/metrics`),
      api.get(`/api/funds/${fundId}/credit`),
      api.get(`/api/funds/${fundId}/maturity`),
      api.get(`/api/funds/${fundId}/holdings`),
    ]).then(([f, m, c, mat, h]) => {
      setFund(f.data)
      setMetrics(m.data)
      setCredit(c.data)
      setMaturity(mat.data)
      setHoldings(h.data)
    }).finally(() => setLoading(false))
  }, [fundId])

  if (loading) return <div className="text-gray-500 text-sm p-8">Loading fund data...</div>
  if (!fund) return <div className="text-gray-500 text-sm p-8">Fund not found.</div>

  const creditData = credit.slice(0, 8).map(r => ({ name: r.rating, value: r.percentage }))
  const maturityData = maturity.map(r => ({ name: r.bucket, value: r.percentage }))

  const keyMetrics = metrics.filter(m =>
    ['aaa_pct', 'expense_ratio', 'aum_crores', 'wam_days', 'lt7d_bucket_pct', 'returns_1y'].includes(m.key)
  )

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
          <button
            onClick={() => navigate(`/chat?fund=${fundId}`)}
            className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors"
          >
            Ask AI about this fund
          </button>
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

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
        {/* Credit Quality */}
        {creditData.length > 0 && (
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <h2 className="text-sm font-semibold text-gray-700 mb-3">Credit Quality</h2>
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie data={creditData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label={({ name, value }) => `${name} ${value?.toFixed(1)}%`} labelLine={false}>
                  {creditData.map(entry => (
                    <Cell key={entry.name} fill={CREDIT_COLORS[entry.name] || '#d1d5db'} />
                  ))}
                </Pie>
                <Tooltip formatter={(v: number) => `${v.toFixed(1)}%`} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Maturity Profile */}
        {maturityData.length > 0 && (
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <h2 className="text-sm font-semibold text-gray-700 mb-3">Maturity Profile</h2>
            <ResponsiveContainer width="100%" height={220}>
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

      {/* Key metrics */}
      {keyMetrics.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 p-4 mb-4">
          <h2 className="text-sm font-semibold text-gray-700 mb-3">Key Metrics</h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            {keyMetrics.map(m => (
              <div key={m.key} className="bg-gray-50 rounded-lg p-3">
                <p className="text-xs text-gray-500">{m.display_name}</p>
                <p className="text-base font-semibold text-gray-800 mt-1">
                  {m.value != null
                    ? `${m.value}${m.unit === 'percentage' ? '%' : m.unit === 'days' ? ' days' : m.unit === 'crores' ? ' Cr' : ''}`
                    : '—'}
                </p>
                <p className="text-xs text-gray-400 mt-0.5">as of {m.extraction_date}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Top holdings */}
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
                <th className="px-4 py-2 text-right font-medium text-gray-500">% of Portfolio</th>
              </tr>
            </thead>
            <tbody>
              {holdings.map((h, i) => (
                <tr key={i} className="border-t border-gray-100 hover:bg-gray-50">
                  <td className="px-4 py-2 text-gray-800">{h.name || h.issuer || '—'}</td>
                  <td className="px-4 py-2 text-gray-500">{h.type || '—'}</td>
                  <td className="px-4 py-2">
                    {h.rating && (
                      <span className="px-2 py-0.5 rounded-full text-xs font-medium" style={{ backgroundColor: `${CREDIT_COLORS[h.rating] || '#d1d5db'}30`, color: CREDIT_COLORS[h.rating] || '#374151' }}>
                        {h.rating}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-2 text-right font-mono text-gray-600">
                    {h.pct != null ? `${h.pct.toFixed(2)}%` : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
