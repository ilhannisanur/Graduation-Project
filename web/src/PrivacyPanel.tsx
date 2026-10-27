import { useEffect, useState, type FormEvent } from 'react'
import { api, ApiError, readError, type Consents } from './api.ts'
import PrivacyNotice from './PrivacyNotice.tsx'

type Props = {
  onSignedOut: () => void
  onAccountDeleted: () => void
}

function errorText(err: unknown): string {
  return err instanceof Error ? err.message : 'Unknown error'
}

export default function PrivacyPanel({ onSignedOut, onAccountDeleted }: Props) {
  const [consents, setConsents] = useState<Consents | null>(null)
  const [consentMessage, setConsentMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [downloading, setDownloading] = useState(false)
  const [password, setPassword] = useState('')
  const [deleting, setDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  useEffect(() => {
    api<Consents>('/api/me/consents')
      .then(setConsents)
      .catch((err: Error) => {
        if (err instanceof ApiError && err.status === 401) onSignedOut()
        else setError(err.message)
      })
  }, [onSignedOut])

  async function setLearning(granted: boolean) {
    setError(null)
    setConsentMessage(null)
    try {
      setConsents(
        await api<Consents>('/api/me/consents', {
          method: 'PUT',
          body: JSON.stringify({ preference_learning: granted }),
        }),
      )
      setConsentMessage(granted ? 'Learning is on.' : 'Learning is off.')
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) onSignedOut()
      else setError(errorText(err))
    }
  }

  async function downloadData() {
    setDownloading(true)
    setError(null)
    try {
      const res = await fetch('/api/me/data')
      if (!res.ok) throw new ApiError(res.status, await readError(res))
      const url = URL.createObjectURL(await res.blob())
      const link = document.createElement('a')
      link.href = url
      link.download = 'my-radio-data.json'
      link.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) onSignedOut()
      else setError(errorText(err))
    } finally {
      setDownloading(false)
    }
  }

  async function deleteAccount(e: FormEvent) {
    e.preventDefault()
    if (!window.confirm('Delete your account and all of your data? This cannot be undone.')) {
      return
    }
    setDeleting(true)
    setDeleteError(null)
    try {
      await api<void>('/api/me', { method: 'DELETE', body: JSON.stringify({ password }) })
      onAccountDeleted()
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) onSignedOut()
      else setDeleteError(errorText(err))
    } finally {
      setDeleting(false)
      setPassword('')
    }
  }

  const learning = consents?.preference_learning
  return (
    <section>
      <h2>Privacy and your data</h2>
      <PrivacyNotice />

      <h3>Learning from your listening</h3>
      {!consents && !error && <p>Loading…</p>}
      {learning && (
        <>
          <label>
            <input
              type="checkbox"
              checked={learning.granted}
              onChange={(e) => setLearning(e.target.checked)}
            />{' '}
            {learning.description}
          </label>
          {learning.updated_at && (
            <p>
              <small>Last changed {new Date(learning.updated_at).toLocaleString()}</small>
            </p>
          )}
        </>
      )}
      {consentMessage && <p role="status">{consentMessage}</p>}

      <h3>Your data</h3>
      <p>Download everything we store about you as a file.</p>
      <button type="button" onClick={downloadData} disabled={downloading}>
        {downloading ? 'Preparing…' : 'Download my data'}
      </button>
      {error && <p role="alert">Error: {error}</p>}

      <h3>Delete your account</h3>
      <p>Your account and all of your data are deleted at once. This cannot be undone.</p>
      <form onSubmit={deleteAccount} style={{ display: 'grid', gap: '0.5rem' }}>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Your password, to confirm"
          autoComplete="current-password"
          required
        />
        <button type="submit" disabled={deleting}>
          {deleting ? 'Deleting…' : 'Delete my account'}
        </button>
      </form>
      {deleteError && <p role="alert">Error: {deleteError}</p>}
    </section>
  )
}
