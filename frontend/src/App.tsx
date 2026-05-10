import { Routes, Route, NavLink, Navigate, useNavigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import {
  MessageSquare, Building2, GitCompare, BarChart3,
  FileText, TrendingUp, LogOut, SlidersHorizontal, ChevronRight,
} from 'lucide-react'
import { AuthProvider, useAuth } from './context/AuthContext'

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 1 } },
})
import Login from './pages/Login'
import Chat from './pages/Chat'
import FundDirectory from './pages/FundDirectory'
import FundDetail from './pages/FundDetail'
import Compare from './pages/Compare'
import Ranking from './pages/Ranking'
import Documents from './pages/Documents'
import RankingProfileEditor from './components/RankingProfileEditor'

const NAV_ITEMS = [
  { to: '/chat',      icon: MessageSquare,   label: 'Chat' },
  { to: '/funds',     icon: Building2,        label: 'Funds' },
  { to: '/compare',   icon: GitCompare,       label: 'Compare' },
  { to: '/ranking',   icon: BarChart3,        label: 'Rankings' },
  { to: '/documents', icon: FileText,         label: 'Documents' },
]

function RankingProfilePage() {
  const navigate = useNavigate()
  return (
    <div className="max-w-2xl">
      <div className="flex items-center gap-2 text-sm text-gray-500 mb-6">
        <button onClick={() => navigate('/ranking')} className="hover:text-gray-700 transition-colors">Rankings</button>
        <ChevronRight size={14} />
        <span className="text-gray-900 font-medium">New Profile</span>
      </div>
      <RankingProfileEditor onSaved={() => navigate('/ranking')} />
    </div>
  )
}

function ProtectedLayout() {
  const { user, loading, logout } = useAuth()
  const navigate = useNavigate()

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-sm text-gray-400">Loading...</div>
      </div>
    )
  }

  if (!user) return <Navigate to="/login" replace />

  return (
    <div className="min-h-screen flex bg-gray-50">
      {/* Sidebar */}
      <aside className="w-56 bg-slate-900 flex flex-col shrink-0">
        {/* Logo */}
        <div className="px-4 py-5 border-b border-slate-800">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 bg-blue-500 rounded-lg flex items-center justify-center shrink-0">
              <TrendingUp size={15} className="text-white" />
            </div>
            <span className="font-bold text-white tracking-tight">RAGAK</span>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
          {NAV_ITEMS.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-blue-600 text-white'
                    : 'text-slate-400 hover:text-white hover:bg-slate-800'
                }`
              }
            >
              <Icon size={16} />
              {label}
            </NavLink>
          ))}
        </nav>

        {/* User */}
        <div className="px-3 py-4 border-t border-slate-800">
          <div className="flex items-center gap-2.5 px-3 py-2 rounded-lg">
            <div className="w-7 h-7 bg-slate-700 rounded-full flex items-center justify-center shrink-0">
              <span className="text-xs font-semibold text-slate-300">
                {user.email[0].toUpperCase()}
              </span>
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium text-white truncate">{user.email}</p>
              <p className="text-xs text-slate-500 capitalize">{user.role}</p>
            </div>
            <button
              onClick={() => { logout(); navigate('/login') }}
              title="Sign out"
              className="text-slate-500 hover:text-slate-300 transition-colors shrink-0"
            >
              <LogOut size={14} />
            </button>
          </div>
        </div>
      </aside>

      {/* Main */}
      <div className="flex-1 flex flex-col min-w-0">
        <main className="flex-1 overflow-auto p-6">
          <Routes>
            <Route path="/" element={<Navigate to="/chat" replace />} />
            <Route path="/chat" element={<Chat />} />
            <Route path="/funds" element={<FundDirectory />} />
            <Route path="/funds/:fundId" element={<FundDetail />} />
            <Route path="/compare" element={<Compare />} />
            <Route path="/ranking" element={<Ranking />} />
            <Route path="/ranking/profiles" element={<RankingProfilePage />} />
            <Route path="/documents" element={<Documents />} />
          </Routes>
        </main>
      </div>
    </div>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginGuard />} />
          <Route path="/*" element={<ProtectedLayout />} />
        </Routes>
      </AuthProvider>
    </QueryClientProvider>
  )
}

function LoginGuard() {
  const { user, loading } = useAuth()
  if (loading) return null
  if (user) return <Navigate to="/chat" replace />
  return <Login />
}
