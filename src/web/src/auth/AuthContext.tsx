import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

import { fetchAuthConfig, fetchAuthSession, loginWithTotp, logoutSession } from '../api/auth'
import { setUnauthorizedHandler } from '../api/client'
import { setLastUsername } from './lastUsername'

type AuthContextValue = {
  loading: boolean
  authenticated: boolean
  privateStackEnabled: boolean
  loginEnabled: boolean
  username: string | null
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
  const [username, setUsername] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      const config = await fetchAuthConfig()
      setPrivateStackEnabled(config.private_stack_enabled)
      setLoginEnabled(config.login_enabled)
      if (!config.private_stack_enabled) {
        setAuthenticated(false)
        setUsername(null)
        return
      }
      const session = await fetchAuthSession()
      setAuthenticated(session.authenticated)
      setLoginEnabled(session.login_enabled)
      setUsername(session.username ?? null)
      if (session.username) {
        setLastUsername(session.username)
      }
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

  // Cualquier 401 de la API (p. ej. sesión caducada a mitad de uso) devuelve al gate de login.
  useEffect(() => {
    setUnauthorizedHandler(() => {
      setAuthenticated(false)
      setUsername(null)
    })
    return () => setUnauthorizedHandler(null)
  }, [])

  const login = useCallback(async (usernameInput: string, totpCode: string) => {
    await loginWithTotp(usernameInput, totpCode)
    setLastUsername(usernameInput)
    // Relee /session con la cookie: si Secure=true en HTTP el navegador no la guarda.
    const session = await fetchAuthSession()
    if (!session.authenticated) {
      setAuthenticated(false)
      setUsername(null)
      throw new Error(
        'Sesión no persistida (cookie bloqueada). En HTTP/staging SESSION_COOKIE_SECURE debe ser false.',
      )
    }
    setAuthenticated(true)
    setUsername(session.username ?? usernameInput)
    setPrivateStackEnabled(session.private_stack_enabled)
    setLoginEnabled(session.login_enabled)
  }, [])

  const logout = useCallback(async () => {
    await logoutSession()
    setAuthenticated(false)
    setUsername(null)
  }, [])

  const value = useMemo(
    () => ({
      loading,
      authenticated,
      privateStackEnabled,
      loginEnabled,
      username,
      login,
      logout,
      refresh,
    }),
    [loading, authenticated, privateStackEnabled, loginEnabled, username, login, logout, refresh],
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
