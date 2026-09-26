import { useState, type FormEvent } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth'
import HandsomeDan from '../components/HandsomeDan'

const MIN_PASSWORD = 8

export default function Signup() {
  const { user, signup } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({ first_name: '', last_name: '', email: '', password: '', confirm: '' })
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  if (user) return <Navigate to="/" replace />

  const set = (field: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [field]: e.target.value }))

  const tooShort = form.password.length > 0 && form.password.length < MIN_PASSWORD
  const mismatch = form.confirm.length > 0 && form.confirm !== form.password

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    if (form.password.length < MIN_PASSWORD) return setError(`Password must be at least ${MIN_PASSWORD} characters.`)
    if (form.password !== form.confirm) return setError('Passwords do not match.')
    setBusy(true)
    try {
      const { confirm: _confirm, ...input } = form
      await signup(input)
      navigate('/')
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth-wrap">
      <aside className="auth-side">
        <HandsomeDan size={96} animated />
        <h2>Join the pack.</h2>
        <ul>
          <li>Your chats are saved, so the assistant remembers what you liked</li>
          <li>It greets you by name when you come back</li>
          <li>Clear your history any time</li>
        </ul>
      </aside>
    <div className="auth-card">
      <h1>Join the pack</h1>
      <p className="muted">Create an account so our assistant remembers what you like.</p>
      <form onSubmit={handleSubmit} className="form">
        <div className="form-row">
          <label>
            First name
            <input name="first_name" required autoComplete="given-name" value={form.first_name} onChange={set('first_name')} />
          </label>
          <label>
            Last name
            <input name="last_name" required autoComplete="family-name" value={form.last_name} onChange={set('last_name')} />
          </label>
        </div>
        <label>
          Email
          <input type="email" name="email" required autoComplete="email" value={form.email} onChange={set('email')} />
        </label>
        <label>
          Password
          <input
            type="password"
            name="password"
            required
            autoComplete="new-password"
            value={form.password}
            onChange={set('password')}
            aria-invalid={tooShort}
          />
          <span className={`hint ${tooShort ? 'bad' : ''}`}>At least {MIN_PASSWORD} characters.</span>
        </label>
        <label>
          Confirm password
          <input
            type="password"
            name="confirm"
            required
            autoComplete="new-password"
            value={form.confirm}
            onChange={set('confirm')}
            aria-invalid={mismatch}
          />
          {mismatch && <span className="hint bad">Passwords don't match.</span>}
        </label>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        <button type="submit" className="btn" disabled={busy}>
          {busy ? 'Creating account…' : 'Create account'}
        </button>
      </form>
      <p className="muted small">
        Already have an account?{' '}
        <Link to="/login" className="link">
          Log in
        </Link>
      </p>
    </div>
    </div>
  )
}
