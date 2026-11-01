import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { AlertTriangle, UserPlus } from 'lucide-react'
import { useAuth } from '../hooks/useAuth'
import { ApiError } from '../services/api'

const MIN_PASSWORD_LENGTH = 8

export default function Register() {
  const { register } = useAuth()

  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [passwordConfirmation, setPasswordConfirmation] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [clientError, setClientError] = useState<string | null>(null)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setSubmitError(null)

    // Checked client-side for immediate feedback — the backend validates
    // all of this again itself (never trust the frontend alone).
    if (password.length < MIN_PASSWORD_LENGTH) {
      setClientError(`Password must be at least ${MIN_PASSWORD_LENGTH} characters long.`)
      return
    }
    if (password !== passwordConfirmation) {
      setClientError('Password and confirmation do not match.')
      return
    }
    setClientError(null)
    setSubmitting(true)
    try {
      await register(name, email, password, passwordConfirmation)
    } catch (err) {
      setSubmitting(false)
      setSubmitError(
        err instanceof ApiError
          ? err.message
          : 'Unable to create an account. Make sure the VISTIQ backend is running.',
      )
    }
  }

  return (
    <section className="mx-auto flex min-h-[70vh] max-w-md flex-col justify-center px-6 py-12">
      <div className="text-center">
        <h1 className="font-heading text-h1 text-primary">Create your account</h1>
        <p className="mt-2 font-body text-body text-secondary">
          Your own private VistiQ wardrobe — only you can see it.
        </p>
      </div>

      <form onSubmit={handleSubmit} noValidate className="mt-8 flex flex-col gap-5 rounded-2xl bg-surface p-6 shadow-sm">
        {(submitError || clientError) && (
          <div role="alert" className="flex items-start gap-2.5 rounded-lg bg-red-50 p-3">
            <AlertTriangle size={16} className="mt-0.5 shrink-0 text-red-600" aria-hidden="true" />
            <p className="font-body text-body-sm text-red-700">{submitError ?? clientError}</p>
          </div>
        )}

        <div className="flex flex-col gap-1.5">
          <label htmlFor="register-name" className="font-label text-label text-primary">
            Name
          </label>
          <input
            id="register-name"
            type="text"
            required
            autoComplete="name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            className="h-11 rounded-lg bg-canvas px-4 font-body text-body text-primary focus:bg-surface focus:shadow-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <label htmlFor="register-email" className="font-label text-label text-primary">
            Email
          </label>
          <input
            id="register-email"
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            className="h-11 rounded-lg bg-canvas px-4 font-body text-body text-primary focus:bg-surface focus:shadow-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <label htmlFor="register-password" className="font-label text-label text-primary">
            Password
          </label>
          <input
            id="register-password"
            type="password"
            required
            autoComplete="new-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            className="h-11 rounded-lg bg-canvas px-4 font-body text-body text-primary focus:bg-surface focus:shadow-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
          />
          <p className="font-body text-body-sm text-secondary">At least {MIN_PASSWORD_LENGTH} characters.</p>
        </div>

        <div className="flex flex-col gap-1.5">
          <label htmlFor="register-password-confirmation" className="font-label text-label text-primary">
            Confirm password
          </label>
          <input
            id="register-password-confirmation"
            type="password"
            required
            autoComplete="new-password"
            value={passwordConfirmation}
            onChange={(event) => setPasswordConfirmation(event.target.value)}
            className="h-11 rounded-lg bg-canvas px-4 font-body text-body text-primary focus:bg-surface focus:shadow-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
          />
        </div>

        <button
          type="submit"
          disabled={submitting}
          className="flex items-center justify-center gap-1.5 rounded-full bg-primary px-6 py-3 font-label text-label text-on-primary shadow-sm transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
        >
          <UserPlus size={18} aria-hidden="true" />
          {submitting ? 'Creating account...' : 'Create Account'}
        </button>

        <p className="text-center font-body text-body-sm text-secondary">
          Already have an account?{' '}
          <Link to="/login" className="font-label text-primary underline-offset-2 hover:underline">
            Log in
          </Link>
        </p>
      </form>
    </section>
  )
}
