import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'

interface Fund {
  id: string
  name: string
  amc_name: string
  category: string | null
  aum_crores: number | null
  expense_ratio: number | null
  nav: number | null
}

export default function FundDirectory() {
  const navigate = useNavigate()
  const [funds, setFunds] = useState<Fund[]>([])
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    setLoading(true)
    api.get('/api/funds').then(r => setFunds(r.data)).finally(() => setLoading(false))
  }, [])

  const displayed = search
    ? funds.filter(f => f.name.toLowerCase().includes(search.toLowerCase()))
    : funds

  return (
    <div className="max-w-5xl mx-auto">
      <h1 className="text-xl font-semibold mb-4">Fund Directory</h1>
      <input
        className="w-full border border-gray-300 rounded-lg px-4 py-2 text-sm mb-4 focus:outline-none focus:ring-2 focus:ring-blue-500"
        placeholder="Search funds..."
        value={search}
        onChange={e => setSearch(e.target.value)}
      />
      {loading ? (
        <p className="text-gray-500 text-sm">Loading...</p>
      ) : (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-4 py-3 text-left font-medium text-gray-600">Fund Name</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">AMC</th>
                <th className="px-4 py-3 text-right font-medium text-gray-600">AUM (Cr)</th>
                <th className="px-4 py-3 text-right font-medium text-gray-600">Expense Ratio</th>
                <th className="px-4 py-3 text-right font-medium text-gray-600">NAV</th>
              </tr>
            </thead>
            <tbody>
              {displayed.map(fund => (
                <tr key={fund.id} onClick={() => navigate(`/funds/${fund.id}`)} className="border-b border-gray-100 hover:bg-gray-50 transition-colors cursor-pointer">
                  <td className="px-4 py-3 font-medium text-blue-700 hover:underline">{fund.name}</td>
                  <td className="px-4 py-3 text-gray-600">{fund.amc_name}</td>
                  <td className="px-4 py-3 text-right text-gray-600">
                    {fund.aum_crores ? `₹${fund.aum_crores.toLocaleString('en-IN')}` : '—'}
                  </td>
                  <td className="px-4 py-3 text-right text-gray-600">
                    {fund.expense_ratio ? `${(fund.expense_ratio * 100).toFixed(2)}%` : '—'}
                  </td>
                  <td className="px-4 py-3 text-right text-gray-600">
                    {fund.nav ? `₹${fund.nav.toFixed(4)}` : '—'}
                  </td>
                </tr>
              ))}
              {displayed.length === 0 && (
                <tr><td colSpan={5} className="px-4 py-8 text-center text-gray-400">No funds found</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
