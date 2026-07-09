import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

import { fetchAuthConfig, fetchAuthSession, loginWithTotp, logoutSession } from '../api/auth'

type AuthContextValue = {
  loading: boolean
  authenticated: boolean
  privateStackEnabled: boolean
  loginEnabled: boolean
  loginUsername: string | null
  login: (username: string, totpCode: string) => Promise<void>
  logout: () => Promise<void>
  refresh: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [loading, setLoading] = useState(true)
  const [authenticated, setAuthenticated] = useState(false)
  const [privateStackEnabled, setPrivateStackEnabled] = useState(false)
  const [loginEnabled, setLoginEnabled] = useState(false)
  const [loginUsername, setLoginUsername] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      const config = await fetchAuthConfig()
      setPrivateStackEnabled(config.private_stack_enabled)
      setLoginEnabled(config.login_enabled)
      setLoginUsername(config.login_username ?? null)
      if (!config.private_stack_enabled) {
        setAuthenticated(false)
        return
      }
      const session = await fetchAuthSession()
      setAuthenticated(session.authenticated)
      setLoginEnabled(session.login_enabled)
    } catch {
      setAuthenticated(false)
    }
  }, [])

  useEffect(() => {
    void (async () => {
      setLoading(true)
      await refresh()
      setLoading(false)
    })()
  }, [refresh])

  const login = useCallback(async (username: string, totpCode: string) => {
    await loginWithTotp(username, totpCode)
    setAuthenticated(true)
  }, [])

  const logout = useCallback(async () => {
    await logoutSession()
    setAuthenticated(false)
  }, [])

  const value = useMemo(
    () => ({
      loading,
      authenticated,
      privateStackEnabled,
      loginEnabled,
      loginUsername,
      login,
      logout,
      refresh,
    }),
    [loading, authenticated, privateStackEnabled, loginEnabled, loginUsername, login, logout, refresh],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error('useAuth debe usarse dentro de AuthProvider')
  }
  return ctx
}
