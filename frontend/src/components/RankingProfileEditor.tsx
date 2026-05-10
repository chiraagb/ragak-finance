import { useState, useEffect } from 'react'
import { api } from '../api/client'

interface MetricDef {
  id: string
  key: string
  display_name: string
  unit: string
  higher_is_better: boolean
  category: string
}

interface WeightMap { [key: string]: number }

interface Props {
  onSaved?: (profileId: string) => void
  cloneFromId?: string
}

const CATEGORIES = ['credit', 'liquidity', 'cost', 'size', 'performance']

export default function RankingProfileEditor({ onSaved, cloneFromId }: Props) {
  const [metrics, setMetrics] = useState<MetricDef[]>([])
  const [weights, setWeights] = useState<WeightMap>({})
  const [locked, setLocked] = useState<Set<string>>(new Set())
  const [name, setName] = useState('')
  const [preview, setPreview] = useState<{ fund_id: string; fund_name: string; total_score: number }[]>([])
  const [saving, setSaving] = useState(false)
  const [previewing, setPreviewing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const total = Object.values(weights).reduce((s, v) => s + v, 0)
  const totalPct = Math.round(total * 100)
  const valid = Math.abs(total - 1.0) <= 0.001

  useEffect(() => {
    api.get('/api/metrics/definitions').then(r => {
      const defs: MetricDef[] = r.data
      setMetrics(defs)
      if (cloneFromId) {
        api.get(`/api/ranking/profiles/${cloneFromId}`).then(pr => {
          const w: WeightMap = {}
          pr.data.weights.forEach((wt: { metric_key: string; weight: number }) => {
            w[wt.metric_key] = wt.weight
          })
          setWeights(w)
          setName(`${pr.data.name} (Copy)`)
        })
      } else {
        const equal = 1 / defs.length
        const init: WeightMap = {}
        defs.forEach(m => { init[m.key] = Math.round(equal * 1000) / 1000 })
        setWeights(init)
      }
    })
  }, [cloneFromId])

  const setWeight = (key: string, pct: number) => {
    const newVal = pct / 100
    const delta = newVal - (weights[key] || 0)
    const unlocked = metrics.map(m => m.key).filter(k => k !== key && !locked.has(k))
    if (unlocked.length === 0) {
      setWeights(prev => ({ ...prev, [key]: newVal }))
      return
    }
    const share = delta / unlocked.length
    setWeights(prev => {
      const next = { ...prev, [key]: newVal }
      unlocked.forEach(k => {
        next[k] = Math.max(0, Math.round((prev[k] - share) * 1000) / 1000)
      })
      return next
    })
  }

  const toggleLock = (key: string) => {
    setLocked(prev => {
      const s = new Set(prev)
      s.has(key) ? s.delete(key) : s.add(key)
      return s
    })
  }

  const handlePreview = async () => {
    if (!valid) return
    setPreviewing(true)
    try {
      const res = await api.post('/api/ranking/profiles/preview', { weights })
      setPreview(res.data.slice(0, 5))
    } catch {
      setPreview([])
    } finally {
      setPreviewing(false)
    }
  }

  const handleSave = async () => {
    if (!valid || !name.trim()) { setError('Name required and weights must sum to 100%'); return }
    setSaving(true)
    setError(null)
    try {
      const res = await api.post('/api/ranking/profiles', { name: name.trim(), weights })
      onSaved?.(res.data.id)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Save failed'
      setError(msg)
    } finally {
      setSaving(false)
    }
  }

  const grouped = CATEGORIES.reduce<Record<string, MetricDef[]>>((acc, cat) => {
    acc[cat] = metrics.filter(m => m.category === cat)
    return acc
  }, {})

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 max-w-2xl">
      <h2 className="text-base font-semibold text-gray-800 mb-4">Ranking Profile Editor</h2>

      <div className="mb-4">
        <label className="text-sm font-medium text-gray-700 mb-1 block">Profile Name</label>
        <input
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="e.g. Conservative Emergency Fund"
          value={name}
          onChange={e => setName(e.target.value)}
        />
      </div>

      <div className={`text-xs mb-3 font-medium ${valid ? 'text-green-600' : 'text-red-500'}`}>
        Total weight: {totalPct}% {valid ? '✓' : `— needs ${100 - totalPct > 0 ? '+' : ''}${100 - totalPct}% more`}
      </div>

      {CATEGORIES.map(cat => (
        grouped[cat]?.length > 0 && (
          <div key={cat} className="mb-4">
            <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2 capitalize">{cat}</div>
            {grouped[cat].map(metric => (
              <div key={metric.key} className="flex items-center gap-3 mb-2">
                <button
                  onClick={() => toggleLock(metric.key)}
                  className={`text-base w-5 shrink-0 ${locked.has(metric.key) ? 'text-amber-500' : 'text-gray-300'}`}
                  title={locked.has(metric.key) ? 'Locked (won\'t auto-balance)' : 'Unlocked (auto-balances)'}
                >
                  {locked.has(metric.key) ? '🔒' : '🔓'}
                </button>
                <span className="text-xs text-gray-700 w-44 shrink-0 truncate" title={metric.display_name}>
                  {metric.display_name}
                </span>
                <input
                  type="range"
                  min={0}
                  max={100}
                  step={1}
                  className="flex-1 accent-blue-600"
                  value={Math.round((weights[metric.key] || 0) * 100)}
                  onChange={e => setWeight(metric.key, Number(e.target.value))}
                />
                <span className="text-xs font-mono text-gray-600 w-10 text-right">
                  {Math.round((weights[metric.key] || 0) * 100)}%
                </span>
              </div>
            ))}
          </div>
        )
      ))}

      {error && <p className="text-xs text-red-500 mb-3">{error}</p>}

      <div className="flex gap-2 mt-4">
        <button
          onClick={handlePreview}
          disabled={!valid || previewing}
          className="px-4 py-2 rounded-lg border border-blue-600 text-blue-600 text-sm font-medium hover:bg-blue-50 disabled:opacity-50 transition-colors"
        >
          {previewing ? 'Loading...' : 'Preview Rankings'}
        </button>
        <button
          onClick={handleSave}
          disabled={!valid || saving || !name.trim()}
          className="px-4 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
        >
          {saving ? 'Saving...' : 'Save Profile'}
        </button>
      </div>

      {preview.length > 0 && (
        <div className="mt-4 border-t border-gray-100 pt-4">
          <div className="text-xs font-medium text-gray-500 mb-2">Preview (top 5)</div>
          <ol className="space-y-1">
            {preview.map((f, i) => (
              <li key={f.fund_id} className="flex justify-between text-xs">
                <span className="text-gray-700">#{i + 1} {f.fund_name || f.fund_id.slice(0, 12)}</span>
                <span className="font-mono text-gray-500">{(f.total_score * 100).toFixed(1)}</span>
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  )
}
