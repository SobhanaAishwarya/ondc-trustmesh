import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import * as authApi from '../api/auth'
import { tokenStore } from '../api/client'
import type { Me } from '../types'

interface AuthContextValue {
  user: Me | null
  isLoading: boolean
  isAuthenticated: boolean
  login: (email: string, password: string) => Promise<Me>
  registerBuyer: (input: authApi.BuyerRegisterInput) => Promise<Me>
  registerSeller: (input: authApi.SellerRegisterInput) => Promise<Me>
  logout: () => void
  refreshUser: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<Me | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const refreshUser = useCallback(async () => {
    if (!tokenStore.getAccess()) {
      setUser(null)
      return
    }
    try {
      const me = await authApi.fetchMe()
      setUser(me)
    } catch {
      tokenStore.clear()
      setUser(null)
    }
  }, [])

  useEffect(() => {
    refreshUser().finally(() => setIsLoading(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    const tokens = await authApi.login(email, password)
    tokenStore.set(tokens.access_token, tokens.refresh_token)
    const me = await authApi.fetchMe()
    setUser(me)
    return me
  }, [])

  const registerBuyer = useCallback(async (input: authApi.BuyerRegisterInput) => {
    const tokens = await authApi.registerBuyer(input)
    tokenStore.set(tokens.access_token, tokens.refresh_token)
    const me = await authApi.fetchMe()
    setUser(me)
    return me
  }, [])

  const registerSeller = useCallback(async (input: authApi.SellerRegisterInput) => {
    const tokens = await authApi.registerSeller(input)
    tokenStore.set(tokens.access_token, tokens.refresh_token)
    const me = await authApi.fetchMe()
    setUser(me)
    return me
  }, [])

  const logout = useCallback(() => {
    const refreshToken = tokenStore.getRefresh()
    tokenStore.clear()
    setUser(null)
    // Best-effort: local sign-out must succeed even if the network call
    // fails, so this fires after clearing local state, not before.
    if (refreshToken) authApi.logoutRequest(refreshToken).catch(() => {})
  }, [])

  return (
    <AuthContext.Provider
      value={{ user, isLoading, isAuthenticated: user !== null, login, registerBuyer, registerSeller, logout, refreshUser }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
