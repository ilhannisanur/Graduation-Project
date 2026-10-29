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
    <details className="notice">
      <summary>How we use your data</summary>
      {error && (
        <p className="alert" role="alert">
          Could not load the privacy notice: {error}
        </p>
      )}
      {notice && (
        <>
          {notice.sections.map((section) => (
            <div key={section.title} className="notice-section">
              <h3>{section.title}</h3>
              <p>{section.text}</p>
            </div>
          ))}
          <p className="meta">Version {notice.version}</p>
        </>
      )}
    </details>
  )
}
