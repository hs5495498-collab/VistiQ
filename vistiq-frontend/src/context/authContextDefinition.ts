import { createContext } from 'react'
import type { AuthUser } from '../services/api'

export interface AuthContextValue {
  user: AuthUser | null
  /** True only during the initial GET /auth/me check on page load —
   * session restoration — so protected routes can wait for it instead of
   * briefly flashing a "please log in" screen before the real answer
   * comes back. */
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  register: (name: string, email: string, password: string, passwordConfirmation: string) => Promise<void>
  logout: () => Promise<void>
}

// Split out of AuthContext.tsx: a file exported by Vite's react-refresh
// plugin may only export components, never also a context object/hook,
// or hot-reloading breaks.
export const AuthContext = createContext<AuthContextValue | null>(null)
