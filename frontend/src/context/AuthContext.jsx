import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { setUnauthorizedHandler, tokenStore } from '../api/client.js'
import { authApi } from '../api/endpoints.js'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(Boolean(tokenStore.get()))

  const logout = useCallback(() => {
    tokenStore.clear()
    setUser(null)
  }, [])

  useEffect(() => {
    setUnauthorizedHandler(logout)
    if (!tokenStore.get()) return
    authApi.me().then(setUser).catch(logout).finally(() => setLoading(false))
  }, [logout])

  const handleToken = (res) => {
    tokenStore.set(res.access_token)
    setUser(res.user)
    return res.user
  }

  const value = useMemo(() => ({
    user,
    loading,
    login: (email, password) => authApi.login({ email, password }).then(handleToken),
    register: (name, email, password) => authApi.register({ name, email, password }).then(handleToken),
    logout,
    updateProfile: (data) => authApi.updateMe(data).then((u) => { setUser(u); return u }),
  }), [user, loading, logout])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export const useAuth = () => {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}
