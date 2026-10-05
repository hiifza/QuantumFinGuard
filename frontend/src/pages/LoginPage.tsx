import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { ApiError } from '../api/client'

export function LoginPage() {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('')
  const [fullName, setFullName] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const { login, register } = useAuth()
  const navigate = useNavigate()

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      if (mode === 'login') {
        await login(email, password)
      } else {
        await register(email, fullName, password)
      }
      navigate('/overview')
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.detail)
      } else {
        setError('Something went wrong.')
      }
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4" style={{ background: 'var(--bg)' }}>
      <div className="w-full max-w-sm">
        <div className="mb-8 flex items-center justify-center gap-2 text-[15px] font-semibold">
          <svg viewBox="0 0 24 24" fill="none" className="h-5 w-5">
            <circle cx="12" cy="12" r="9" stroke="var(--emerald)" strokeWidth="1.4" />
            <circle cx="12" cy="12" r="2.4" fill="var(--amber)" />
          </svg>
          QuantumFinGuard
        </div>

        <div
          className="rounded-[var(--radius)] border p-7"
          style={{
            background: 'var(--surface)',
            borderColor: 'var(--line)',
            boxShadow: '0 1px 0 0 rgba(255,255,255,0.03) inset, 0 10px 28px -10px rgba(0,0,0,0.4)',
          }}
        >
          <h1 className="font-serif text-xl" style={{ color: 'var(--text)' }}>
            {mode === 'login' ? 'Sign in' : 'Create an account'}
          </h1>
          <p className="mt-1 text-[13px]" style={{ color: 'var(--text-dim)' }}>
            {mode === 'login' ? 'Access the investigation platform.' : 'Analyst accounts start at the base role.'}
          </p>

          <form onSubmit={handleSubmit} className="mt-6 space-y-3.5">
            {mode === 'register' && (
              <div>
                <label className="mb-1.5 block text-xs" style={{ color: 'var(--text-dim)' }}>
                  Full name
                </label>
                <input
                  required
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  className="w-full rounded-md border px-3 py-2 text-sm outline-none"
                  style={{ background: 'var(--surface-2)', borderColor: 'var(--line)', color: 'var(--text)' }}
                />
              </div>
            )}
            <div>
              <label className="mb-1.5 block text-xs" style={{ color: 'var(--text-dim)' }}>
                Email
              </label>
              <input
                required
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full rounded-md border px-3 py-2 text-sm outline-none"
                style={{ background: 'var(--surface-2)', borderColor: 'var(--line)', color: 'var(--text)' }}
              />
            </div>
            <div>
              <label className="mb-1.5 block text-xs" style={{ color: 'var(--text-dim)' }}>
                Password
              </label>
              <input
                required
                type="password"
                minLength={10}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-md border px-3 py-2 text-sm outline-none"
                style={{ background: 'var(--surface-2)', borderColor: 'var(--line)', color: 'var(--text)' }}
              />
              {mode === 'register' && (
                <p className="mt-1 text-[11px]" style={{ color: 'var(--text-dim)' }}>
                  Minimum 10 characters.
                </p>
              )}
            </div>

            {error && (
              <div className="rounded-md px-3 py-2 text-[12.5px]" style={{ background: 'var(--coral-soft)', color: 'var(--coral)' }}>
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={submitting}
              className="w-full rounded-md py-2.5 text-sm font-semibold transition-opacity disabled:opacity-60"
              style={{ background: 'var(--emerald)', color: '#0A0E13' }}
            >
              {submitting ? 'Please wait…' : mode === 'login' ? 'Sign in' : 'Create account'}
            </button>
          </form>

          <button
            onClick={() => {
              setMode(mode === 'login' ? 'register' : 'login')
              setError(null)
            }}
            className="mt-5 w-full text-center text-[12.5px]"
            style={{ color: 'var(--text-dim)' }}
          >
            {mode === 'login' ? "Don't have an account? " : 'Already have an account? '}
            <span style={{ color: 'var(--emerald)' }}>{mode === 'login' ? 'Create one' : 'Sign in'}</span>
          </button>
        </div>
      </div>
    </div>
  )
}
