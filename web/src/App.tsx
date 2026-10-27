import { useCallback, useEffect, useState } from 'react'
import { api, type User } from './api.ts'
import AuthPanel from './AuthPanel.tsx'
import DevPanel from './DevPanel.tsx'
import ProfilePanel from './ProfilePanel.tsx'

export default function App() {
  // undefined: still checking whether a login cookie is valid
  const [user, setUser] = useState<User | null | undefined>(undefined)

  useEffect(() => {
    api<User>('/api/me')
      .then(setUser)
      .catch(() => setUser(null))
  }, [])

  const signedOut = useCallback(() => setUser(null), [])

  async function logout() {
    try {
      await api<void>('/api/auth/logout', { method: 'POST' })
    } finally {
      setUser(null)
    }
  }

  return (
    <main
      style={{ maxWidth: 560, margin: '2rem auto', padding: '0 1rem', fontFamily: 'sans-serif' }}
    >
      <h1>Emotion-Aware AI Radio</h1>

      {user === undefined && <p>Loading…</p>}
      {user === null && <AuthPanel onLoggedIn={setUser} />}
      {user && (
        <>
          <p>
            Signed in as <strong>{user.username}</strong>{' '}
            <button type="button" onClick={logout}>
              Sign out
            </button>
          </p>
          <ProfilePanel onSignedOut={signedOut} />
        </>
      )}

      <DevPanel />
    </main>
  )
}
