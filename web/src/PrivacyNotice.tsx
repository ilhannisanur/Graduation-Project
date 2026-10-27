import { useEffect, useState } from 'react'
import { api, type PrivacyNotice as Notice } from './api.ts'

/** "How we use your data", folded by default. The text comes from the backend. */
export default function PrivacyNotice() {
  const [notice, setNotice] = useState<Notice | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api<Notice>('/api/privacy')
      .then(setNotice)
      .catch((err: Error) => setError(err.message))
  }, [])

  return (
    <details>
      <summary>How we use your data</summary>
      {error && <p role="alert">Could not load the privacy notice: {error}</p>}
      {notice && (
        <>
          {notice.sections.map((section) => (
            <div key={section.title}>
              <h4 style={{ marginBottom: '0.25rem' }}>{section.title}</h4>
              <p style={{ marginTop: 0 }}>{section.text}</p>
            </div>
          ))}
          <p>
            <small>Version {notice.version}</small>
          </p>
        </>
      )}
    </details>
  )
}
