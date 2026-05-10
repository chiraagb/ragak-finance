import { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import { api } from '../api/client'

interface User { id: string; email: string; role: string }
interface AuthContextValue {
  user: User | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const token = localStorage.getItem('access_token')
    if (!token) { setLoading(false); return }
    api.get('/api/auth/me')
      .then(r => setUser(r.data))
      .catch(() => localStorage.removeItem('access_token'))
      .finally(() => setLoading(false))
  }, [])

  const login = async (email: string, password: string) => {
    const r = await api.post('/api/auth/login', { email, password })
    localStorage.setItem('access_token', r.data.access_token)
    const me = await api.get('/api/auth/me')
    setUser(me.data)
  }

  const register = async (email: string, password: string) => {
    const r = await api.post('/api/auth/register', { email, password })
    localStorage.setItem('access_token', r.data.access_token)
    const me = await api.get('/api/auth/me')
    setUser(me.data)
  }

  const logout = () => {
    localStorage.removeItem('access_token')
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
