import { useState, type FormEvent } from 'react'
import { api, type User } from './api.ts'
import PasswordInput from './PasswordInput.tsx'
import PrivacyNotice from './PrivacyNotice.tsx'

type Mode = 'login' | 'register'

// Uppercase and the Turkish İ/ı are allowed here: the backend turns them into plain
// lowercase letters before checking (NİSA -> nisa).
const USERNAME_PATTERN = '[A-Za-z0-9_.\\-İı]{3,32}'
const USERNAME_RULE = "3-32 characters: letters, digits, '.', '_' or '-'. No spaces."

export default function AuthPanel({ onLoggedIn }: { onLoggedIn: (user: User) => void }) {
  const [mode, setMode] = useState<Mode>('login')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  // Optional consent: never ticked in advance.
  const [learning, setLearning] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const body =
        mode === 'register'
          ? { username, password, preference_learning: learning }
          : { username, password }
      const user = await api<User>(`/api/auth/${mode}`, {
        method: 'POST',
        body: JSON.stringify(body),
      })
      setPassword('')
      onLoggedIn(user)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setBusy(false)
    }
  }

  function switchMode() {
    setMode(mode === 'login' ? 'register' : 'login')
    setError(null)
  }

  const registering = mode === 'register'
  return (
    <section className="auth-card" aria-labelledby="auth-title">
      <div style={{ display: 'grid', gap: 6 }}>
        <h2 id="auth-title">{registering ? 'Start your station' : 'Welcome back'}</h2>
        <p className="muted">
          {registering ? 'Pick a name and a password.' : 'Sign in to hear your radio.'}
        </p>
      </div>
      <form onSubmit={submit}>
        {/* The hints sit outside the <label> so the field's name stays "Username" / "Password". */}
        <div className="field">
          <label htmlFor="auth-username">Username</label>
          <input
            id="auth-username"
            className="input"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            // Same rule as the backend; the browser points at this field before sending.
            pattern={registering ? USERNAME_PATTERN : undefined}
            title={registering ? USERNAME_RULE : undefined}
            aria-describedby={registering ? 'username-rule' : undefined}
            required
          />
          {registering && (
            <span id="username-rule" className="field-hint">
              {USERNAME_RULE}
            </span>
          )}
        </div>
        <div className="field">
          <label htmlFor="auth-password">Password</label>
          <PasswordInput
            id="auth-password"
            value={password}
            onChange={setPassword}
            autoComplete={registering ? 'new-password' : 'current-password'}
            minLength={registering ? 8 : undefined}
            describedBy={registering ? 'password-rule' : undefined}
          />
          {registering && (
            <span id="password-rule" className="field-hint">
              At least 8 characters.
            </span>
          )}
        </div>
        {registering && (
          <>
            <label className="switch-row tone-mint">
              <span>
                <strong>Learn from what I listen to</strong>
                <span className="muted">Optional. You can change this later.</span>
              </span>
              <input
                type="checkbox"
                role="switch"
                className="switch"
                checked={learning}
                onChange={(e) => setLearning(e.target.checked)}
              />
            </label>
            <PrivacyNotice />
          </>
        )}
        {error && (
          <p className="alert" role="alert">
            {error}
          </p>
        )}
        <button type="submit" className="btn btn-primary btn-big" disabled={busy}>
          {busy ? 'Please wait…' : registering ? 'Create account' : 'Sign in'}
        </button>
      </form>
      <p className="muted">
        {registering ? 'Already have an account?' : 'New here?'}{' '}
        <button type="button" className="link-btn" onClick={switchMode}>
          {registering ? 'Sign in' : 'Create an account'}
        </button>
      </p>
    </section>
  )
}
