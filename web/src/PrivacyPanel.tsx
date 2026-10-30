import { useEffect, useRef, useState, type FormEvent } from 'react'
import { api, ApiError, readError, type Consents } from './api.ts'
import PrivacyNotice from './PrivacyNotice.tsx'
import Banner from './Banner.tsx'
import PasswordInput from './PasswordInput.tsx'
import Setting from './Setting.tsx'

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
  const confirmRef = useRef<HTMLDialogElement>(null)

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

  // The form only asks; the dialog's button does the deleting.
  function askToDelete(e: FormEvent) {
    e.preventDefault()
    setDeleteError(null)
    confirmRef.current?.showModal()
  }

  async function deleteAccount() {
    confirmRef.current?.close()
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
    <>
      <Banner tone="mint" title="Privacy and your data">
        What we keep about you, and how to take it with you or remove it. You are in control.
      </Banner>

      <Setting
        title="Learning from your listening"
        tone="mint"
        description="Saved as soon as you switch it. Your profile works either way."
      >
        {!consents && !error && <div className="skeleton" aria-label="Loading" />}
        {learning && (
          <label className="switch-row">
            <span>
              <strong>Learn from what I listen to</strong>
              <span className="muted">{learning.description}</span>
              {learning.updated_at && (
                <span className="meta">
                  Last changed {new Date(learning.updated_at).toLocaleString()}
                </span>
              )}
            </span>
            <input
              type="checkbox"
              role="switch"
              className="switch"
              checked={learning.granted}
              onChange={(e) => setLearning(e.target.checked)}
            />
          </label>
        )}
        {consentMessage && (
          <p className="status" role="status">
            {consentMessage}
          </p>
        )}
        <PrivacyNotice />
      </Setting>

      <Setting
        title="Your data"
        description="Everything we store about you, as one JSON file."
        tone="sky"
      >
        <div className="panel-actions" style={{ justifyContent: 'space-between' }}>
          <span className="muted">my-radio-data.json</span>
          <button type="button" className="btn" onClick={downloadData} disabled={downloading}>
            {downloading ? 'Preparing…' : 'Download my data'}
          </button>
        </div>
        {error && (
          <p className="alert" role="alert">
            {error}
          </p>
        )}
      </Setting>

      <Setting
        title="Delete your account"
        description="Your account and all of your data are deleted at once. This cannot be undone."
      >
        <form onSubmit={askToDelete} style={{ display: 'grid', gap: 16 }}>
          <div className="field">
            <label htmlFor="delete-password">Your password, to confirm</label>
            <PasswordInput
              id="delete-password"
              value={password}
              onChange={setPassword}
              autoComplete="current-password"
            />
          </div>
          {deleteError && (
            <p className="alert" role="alert">
              {deleteError}
            </p>
          )}
          <div className="panel-actions">
            <button type="submit" className="btn btn-danger" disabled={deleting}>
              {deleting ? 'Deleting…' : 'Delete my account'}
            </button>
          </div>
        </form>
      </Setting>

      <dialog
        ref={confirmRef}
        className="dialog"
        aria-labelledby="delete-title"
        aria-describedby="delete-text"
      >
        <h2 id="delete-title">Delete your account?</h2>
        <p id="delete-text" className="muted">
          Your account and everything we store about you are removed for good. This cannot be
          undone.
        </p>
        <div className="panel-actions">
          <button
            type="button"
            className="btn"
            autoFocus
            onClick={() => confirmRef.current?.close()}
          >
            Keep my account
          </button>
          <button type="button" className="btn btn-danger-fill" onClick={deleteAccount}>
            Yes, delete everything
          </button>
        </div>
      </dialog>
    </>
  )
}
