import { useState, type FormEvent } from 'react'
import { api, type User } from './api.ts'

type Mode = 'login' | 'register'

// Uppercase and the Turkish İ/ı are allowed here: the backend turns them into plain
// lowercase letters before checking (NİSA -> nisa).
const USERNAME_PATTERN = '[A-Za-z0-9_.\\-İı]{3,32}'
const USERNAME_RULE = "3-32 characters: letters, digits, '.', '_' or '-'. No spaces."

export default function AuthPanel({ onLoggedIn }: { onLoggedIn: (user: User) => void }) {
  const [mode, setMode] = useState<Mode>('login')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const user = await api<User>(`/api/auth/${mode}`, {
        method: 'POST',
        body: JSON.stringify({ username, password }),
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
    <section>
      <h2>{registering ? 'Create an account' : 'Sign in'}</h2>
      <form onSubmit={submit} style={{ display: 'grid', gap: '0.5rem' }}>
        <input
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          placeholder="Username"
          autoComplete="username"
          // Same rule as the backend; the browser points at this field before sending.
          pattern={registering ? USERNAME_PATTERN : undefined}
          title={registering ? USERNAME_RULE : undefined}
          aria-describedby={registering ? 'username-rule' : undefined}
          required
        />
        {registering && (
          <small id="username-rule" style={{ marginTop: '-0.25rem' }}>
            {USERNAME_RULE}
          </small>
        )}
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder={registering ? 'Password (at least 8 characters)' : 'Password'}
          autoComplete={registering ? 'new-password' : 'current-password'}
          minLength={registering ? 8 : undefined}
          required
        />
        <button type="submit" disabled={busy}>
          {busy ? 'Please wait…' : registering ? 'Create account' : 'Sign in'}
        </button>
      </form>
      {error && <p role="alert">Error: {error}</p>}
      <p>
        {registering ? 'Already have an account?' : 'New here?'}{' '}
        <button type="button" onClick={switchMode}>
          {registering ? 'Sign in' : 'Create an account'}
        </button>
      </p>
    </section>
  )
}
