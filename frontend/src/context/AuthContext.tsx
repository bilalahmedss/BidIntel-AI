import { createContext, useContext, useState, ReactNode } from 'react'

interface User { id: number; email: string; full_name: string }
interface AuthCtx { user: User | null; token: string | null; login(token: string, user: User): void; logout(): void }

const AuthContext = createContext<AuthCtx>(null!)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('bi_token'))
  const [user, setUser] = useState<User | null>(() => {
    const u = localStorage.getItem('bi_user')
    return u ? JSON.parse(u) : null
  })

  function login(t: string, u: User) {
    localStorage.setItem('bi_token', t)
    localStorage.setItem('bi_user', JSON.stringify(u))
    setToken(t); setUser(u)
  }
  function logout() {
    localStorage.removeItem('bi_token'); localStorage.removeItem('bi_user')
    setToken(null); setUser(null)
  }
  return <AuthContext.Provider value={{ user, token, login, logout }}>{children}</AuthContext.Provider>
}

export function useAuth() { return useContext(AuthContext) }
