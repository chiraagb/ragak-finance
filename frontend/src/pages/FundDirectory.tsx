import { useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { useFunds } from '../hooks/useFunds'

type SortKey = 'aum_crores' | 'expense_ratio' | 'name'
type SortDir = 'asc' | 'desc'

export default function FundDirectory() {
  const navigate = useNavigate()
  const [search, setSearch] = useState('')
  const [categoryFilter, setCategoryFilter] = useState('')
  const [amcFilter, setAmcFilter] = useState('')
  const [sortKey, setSortKey] = useState<SortKey>('aum_crores')
  const [sortDir, setSortDir] = useState<SortDir>('desc')

  const { data: funds = [], isLoading: loading } = useFunds()

  const categories = useMemo(() => Array.from(new Set(funds.map(f => f.category).filter(Boolean))).sort() as string[], [funds])
  const amcs = useMemo(() => Array.from(new Set(funds.map(f => f.amc_name).filter(Boolean))).sort(), [funds])

  const displayed = useMemo(() => {
    let result = funds
    if (search) result = result.filter(f => f.name.toLowerCase().includes(search.toLowerCase()) || f.amc_name.toLowerCase().includes(search.toLowerCase()))
    if (categoryFilter) result = result.filter(f => f.category === categoryFilter)
    if (amcFilter) result = result.filter(f => f.amc_name === amcFilter)
    result = [...result].sort((a, b) => {
      const av = a[sortKey] ?? (sortKey === 'name' ? '' : -Infinity)
      const bv = b[sortKey] ?? (sortKey === 'name' ? '' : -Infinity)
      if (typeof av === 'string' && typeof bv === 'string') return sortDir === 'asc' ? av.localeCompare(bv) : bv.localeCompare(av)
      return sortDir === 'asc' ? (av as number) - (bv as number) : (bv as number) - (av as number)
    })
    return result
  }, [funds, search, categoryFilter, amcFilter, sortKey, sortDir])

  function toggleSort(key: SortKey) {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortKey(key); setSortDir('desc') }
  }

  function SortIcon({ k }: { k: SortKey }) {
    if (sortKey !== k) return <span className="text-gray-300 ml-1">↕</span>
    return <span className="text-blue-500 ml-1">{sortDir === 'asc' ? '↑' : '↓'}</span>
  }

  return (
    <div className="max-w-5xl mx-auto">
      <h1 className="text-xl font-semibold mb-4">Fund Directory</h1>

      {/* Filter bar */}
      <div className="flex flex-wrap gap-2 mb-4">
        <input
          className="flex-1 min-w-[180px] border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="Search by name or AMC..."
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
        <select
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          value={categoryFilter}
          onChange={e => setCategoryFilter(e.target.value)}
        >
          <option value="">All Categories</option>
          {categories.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
        <select
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 max-w-[200px]"
          value={amcFilter}
          onChange={e => setAmcFilter(e.target.value)}
        >
          <option value="">All AMCs</option>
          {amcs.map(a => <option key={a} value={a}>{a}</option>)}
        </select>
        {(categoryFilter || amcFilter || search) && (
          <button
            onClick={() => { setSearch(''); setCategoryFilter(''); setAmcFilter('') }}
            className="px-3 py-2 text-sm text-gray-500 hover:text-gray-700 border border-gray-300 rounded-lg"
          >
            Clear
          </button>
        )}
      </div>

      <p className="text-xs text-gray-400 mb-2">{displayed.length} fund{displayed.length !== 1 ? 's' : ''}</p>

      {loading ? (
        <p className="text-gray-500 text-sm">Loading...</p>
      ) : (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-4 py-3 text-left font-medium text-gray-600 cursor-pointer select-none" onClick={() => toggleSort('name')}>
                  Fund Name <SortIcon k="name" />
                </th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">AMC</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">Category</th>
                <th className="px-4 py-3 text-right font-medium text-gray-600 cursor-pointer select-none" onClick={() => toggleSort('aum_crores')}>
                  AUM (Cr) <SortIcon k="aum_crores" />
                </th>
                <th className="px-4 py-3 text-right font-medium text-gray-600 cursor-pointer select-none" onClick={() => toggleSort('expense_ratio')}>
                  Expense <SortIcon k="expense_ratio" />
                </th>
                <th className="px-4 py-3 text-right font-medium text-gray-600">NAV</th>
              </tr>
            </thead>
            <tbody>
              {displayed.map(fund => (
                <tr key={fund.id} onClick={() => navigate(`/funds/${fund.id}`)} className="border-b border-gray-100 hover:bg-gray-50 transition-colors cursor-pointer">
                  <td className="px-4 py-3 font-medium text-blue-700 hover:underline max-w-xs truncate">{fund.name}</td>
                  <td className="px-4 py-3 text-gray-600 truncate max-w-[120px]">{fund.amc_name}</td>
                  <td className="px-4 py-3 text-gray-500 text-xs">
                    {fund.category && (
                      <span className="px-2 py-0.5 bg-gray-100 rounded-full">{fund.category}</span>
                    )}
                  </td>
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
                <tr><td colSpan={6} className="px-4 py-8 text-center text-gray-400">No funds match your filters</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
