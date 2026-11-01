import { useEffect, useState, type ReactNode } from 'react'
import { ApiError, getCurrentUser, loginUser, logoutUser, registerUser, type AuthUser } from '../services/api'
import { AuthContext } from './authContextDefinition'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [loading, setLoading] = useState(true)

  // Session restoration on page refresh: the frontend holds no auth state
  // of its own to persist — it asks the backend, once, on mount, since
  // the HttpOnly session cookie (if any) is the only real source of truth.
  useEffect(() => {
    let cancelled = false
    getCurrentUser()
      .then((currentUser) => {
        if (!cancelled) setUser(currentUser)
      })
      .catch(() => {
        if (!cancelled) setUser(null)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  async function login(email: string, password: string) {
    const loggedInUser = await loginUser({ email, password })
    // Full reload rather than just setUser(...): guarantees every
    // page/hook's already-fetched state (wardrobe items, recommendations)
    // is thrown away and refetched fresh for the new account — the
    // simplest reliable way to satisfy "clear any user-specific frontend
    // state when the account changes" without a larger state-management
    // system.
    setUser(loggedInUser)
    window.location.assign('/wardrobe')
  }

  async function register(name: string, email: string, password: string, passwordConfirmation: string) {
    const newUser = await registerUser({ name, email, password, passwordConfirmation })
    setUser(newUser)
    window.location.assign('/wardrobe')
  }

  async function logout() {
    try {
      await logoutUser()
    } catch (err) {
      // A logout call failing (e.g. session already expired server-side)
      // must still clear local state and send the user to a logged-out
      // screen — never leave them stuck on a "logging out..." state.
      if (!(err instanceof ApiError)) throw err
    }
    window.location.assign('/login')
  }

  return <AuthContext.Provider value={{ user, loading, login, register, logout }}>{children}</AuthContext.Provider>
}
