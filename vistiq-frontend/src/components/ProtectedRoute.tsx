import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'

/** Wraps a page that requires a logged-in user. Waits for the initial
 * GET /auth/me session-restoration check (see AuthContext) before
 * deciding — otherwise a logged-in user would briefly flash a redirect
 * to /login on every page refresh, before the real answer comes back. */
export default function ProtectedRoute({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()
  const location = useLocation()

  if (loading) {
    return (
      <section className="mx-auto max-w-2xl px-6 py-20 text-center">
        <p className="font-body text-body text-secondary">Loading...</p>
      </section>
    )
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  return <>{children}</>
}
