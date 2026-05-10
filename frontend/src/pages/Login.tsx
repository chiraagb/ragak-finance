import { useState, FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { TrendingUp, Shield, BarChart3 } from 'lucide-react'

export default function Login() {
  const { login, register } = useAuth()
  const navigate = useNavigate()
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      if (mode === 'login') await login(email, password)
      else await register(email, password)
      navigate('/chat')
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(detail || (mode === 'login' ? 'Invalid credentials' : 'Registration failed'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-blue-900 flex">
      {/* Left panel — branding */}
      <div className="hidden lg:flex flex-col justify-between w-1/2 p-12 text-white">
        <div>
          <div className="flex items-center gap-2 mb-12">
            <div className="w-8 h-8 bg-blue-500 rounded-lg flex items-center justify-center">
              <TrendingUp size={18} className="text-white" />
            </div>
            <span className="text-xl font-bold tracking-tight">RAGAK</span>
          </div>
          <h1 className="text-4xl font-bold leading-tight mb-4">
            AI-powered mutual fund intelligence
          </h1>
          <p className="text-slate-300 text-lg leading-relaxed">
            Analyze credit quality, compare funds, and get instant answers from factsheets — all in one place.
          </p>
        </div>

        <div className="space-y-4">
          {[
            { icon: BarChart3, title: 'Configurable Rankings', desc: 'Weight metrics your way — AAA %, expense ratio, AUM' },
            { icon: Shield, title: 'Credit-First Analysis', desc: 'Sovereign, AAA, and issuer concentration at a glance' },
            { icon: TrendingUp, title: 'AI Chat on Factsheets', desc: 'Ask questions directly about uploaded fund documents' },
          ].map(({ icon: Icon, title, desc }) => (
            <div key={title} className="flex items-start gap-3 p-4 bg-white/5 rounded-xl border border-white/10">
              <div className="w-8 h-8 bg-blue-500/20 rounded-lg flex items-center justify-center shrink-0 mt-0.5">
                <Icon size={16} className="text-blue-400" />
              </div>
              <div>
                <p className="font-medium text-sm">{title}</p>
                <p className="text-slate-400 text-xs mt-0.5">{desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Right panel — form */}
      <div className="flex-1 flex items-center justify-center p-6">
        <div className="w-full max-w-sm">
          {/* Mobile logo */}
          <div className="flex items-center gap-2 mb-8 lg:hidden">
            <div className="w-8 h-8 bg-blue-500 rounded-lg flex items-center justify-center">
              <TrendingUp size={18} className="text-white" />
            </div>
            <span className="text-xl font-bold text-white tracking-tight">RAGAK</span>
          </div>

          <div className="bg-white rounded-2xl shadow-2xl p-8">
            <h2 className="text-xl font-bold text-gray-900 mb-1">
              {mode === 'login' ? 'Welcome back' : 'Create your account'}
            </h2>
            <p className="text-sm text-gray-500 mb-6">
              {mode === 'login' ? 'Sign in to your workspace' : 'Get started for free'}
            </p>

            <form onSubmit={submit} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1.5">Email address</label>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1.5">Password</label>
                <input
                  type="password"
                  required
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
                />
              </div>

              {error && (
                <div className="bg-red-50 border border-red-200 rounded-lg px-3 py-2.5 text-xs text-red-600">
                  {error}
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white font-medium py-2.5 rounded-lg text-sm transition-colors"
              >
                {loading ? 'Please wait...' : mode === 'login' ? 'Sign in' : 'Create account'}
              </button>
            </form>

            <p className="text-center text-xs text-gray-500 mt-5">
              {mode === 'login' ? "Don't have an account? " : 'Already have an account? '}
              <button
                onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError(null) }}
                className="text-blue-600 font-medium hover:underline"
              >
                {mode === 'login' ? 'Sign up' : 'Sign in'}
              </button>
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
