import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { authApi } from '../api/endpoints'
import { getStoredTokens, setStoredTokens } from '../api/client'
import type { UserOut } from '../api/types'

interface AuthContextValue {
  user: UserOut | null
  isLoading: boolean
  isAuthenticated: boolean
  login: (email: string, password: string) => Promise<void>
  register: (email: string, fullName: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserOut | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const loadCurrentUser = useCallback(async () => {
    const tokens = getStoredTokens()
    if (!tokens) {
      setUser(null)
      setIsLoading(false)
      return
    }
    try {
      const me = await authApi.me()
      setUser(me)
    } catch {
      setStoredTokens(null)
      setUser(null)
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    loadCurrentUser()

    const handleExpired = () => {
      setUser(null)
    }
    window.addEventListener('qfg:session-expired', handleExpired)
    return () => window.removeEventListener('qfg:session-expired', handleExpired)
  }, [loadCurrentUser])

  const login = useCallback(async (email: string, password: string) => {
    const tokens = await authApi.login({ email, password })
    setStoredTokens(tokens)
    const me = await authApi.me()
    setUser(me)
  }, [])

  const register = useCallback(async (email: string, fullName: string, password: string) => {
    await authApi.register({ email, full_name: fullName, password })
    await login(email, password)
  }, [login])

  const logout = useCallback(() => {
    setStoredTokens(null)
    setUser(null)
  }, [])

  return (
    <AuthContext.Provider value={{ user, isLoading, isAuthenticated: !!user, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
