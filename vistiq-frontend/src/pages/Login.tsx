import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { AlertTriangle, LogIn } from 'lucide-react'
import { useAuth } from '../hooks/useAuth'
import { ApiError } from '../services/api'

export default function Login() {
  const { login } = useAuth()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setSubmitError(null)
    setSubmitting(true)
    try {
      await login(email, password)
    } catch (err) {
      setSubmitting(false)
      setSubmitError(
        err instanceof ApiError
          ? err.message
          : 'Unable to log in. Make sure the VISTIQ backend is running.',
      )
    }
  }

  return (
    <section className="mx-auto flex min-h-[70vh] max-w-md flex-col justify-center px-6 py-12">
      <div className="text-center">
        <h1 className="font-heading text-h1 text-primary">Welcome back</h1>
        <p className="mt-2 font-body text-body text-secondary">Log in to your VistiQ wardrobe.</p>
      </div>

      <form onSubmit={handleSubmit} noValidate className="mt-8 flex flex-col gap-5 rounded-2xl bg-surface p-6 shadow-sm">
        {submitError && (
          <div role="alert" className="flex items-start gap-2.5 rounded-lg bg-red-50 p-3">
            <AlertTriangle size={16} className="mt-0.5 shrink-0 text-red-600" aria-hidden="true" />
            <p className="font-body text-body-sm text-red-700">{submitError}</p>
          </div>
        )}

        <div className="flex flex-col gap-1.5">
          <label htmlFor="login-email" className="font-label text-label text-primary">
            Email
          </label>
          <input
            id="login-email"
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            className="h-11 rounded-lg bg-canvas px-4 font-body text-body text-primary focus:bg-surface focus:shadow-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <label htmlFor="login-password" className="font-label text-label text-primary">
            Password
          </label>
          <input
            id="login-password"
            type="password"
            required
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            className="h-11 rounded-lg bg-canvas px-4 font-body text-body text-primary focus:bg-surface focus:shadow-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
          />
        </div>

        <button
          type="submit"
          disabled={submitting}
          className="flex items-center justify-center gap-1.5 rounded-full bg-primary px-6 py-3 font-label text-label text-on-primary shadow-sm transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
        >
          <LogIn size={18} aria-hidden="true" />
          {submitting ? 'Logging in...' : 'Log In'}
        </button>

        <p className="text-center font-body text-body-sm text-secondary">
          New to VistiQ?{' '}
          <Link to="/register" className="font-label text-primary underline-offset-2 hover:underline">
            Create an account
          </Link>
        </p>
      </form>
    </section>
  )
}
