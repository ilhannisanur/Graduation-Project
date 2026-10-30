import { useEffect, useState, type FormEvent } from 'react'
import { readError } from './api.ts'
import Setting from './Setting.tsx'

type Health = { app: string; db: string }

/** Developer checks: backend status and a DJ announcement preview. */
export default function DevPanel() {
  const [health, setHealth] = useState<Health | null>(null)
  const [healthError, setHealthError] = useState<string | null>(null)

  const [title, setTitle] = useState('Midnight Rain')
  const [artist, setArtist] = useState('The Night Owls')
  const [mood, setMood] = useState('calm')
  const [loading, setLoading] = useState(false)
  const [announcement, setAnnouncement] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch('/api/health')
      .then((res) => (res.ok ? res.json() : Promise.reject(new Error(`HTTP ${res.status}`))))
      .then(setHealth)
      .catch((e: Error) => setHealthError(e.message))
  }, [])

  async function generate(e: FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError(null)
    setAnnouncement(null)
    try {
      const res = await fetch('/api/dj/preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title, artist, mood }),
      })
      if (!res.ok) throw new Error(await readError(res))
      setAnnouncement((await res.json()).announcement)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <Setting title="Backend status" description="The API and its database.">
        {healthError && (
          <p className="alert" role="alert">
            Backend unreachable: {healthError}
          </p>
        )}
        {health && (
          <p>
            App: <strong>{health.app}</strong> · Database: <strong>{health.db}</strong>
          </p>
        )}
        {!health && !healthError && <p className="muted">Checking…</p>}
      </Setting>

      <Setting
        title="DJ announcement preview"
        tone="lime"
        description="Asks the language model for one song introduction."
      >
        <form onSubmit={generate} style={{ display: 'grid', gap: 16 }}>
          <label className="field">
            Title
            <input
              className="input"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              required
            />
          </label>
          <label className="field">
            Artist
            <input
              className="input"
              value={artist}
              onChange={(e) => setArtist(e.target.value)}
              required
            />
          </label>
          <label className="field">
            Mood
            <input
              className="input"
              value={mood}
              onChange={(e) => setMood(e.target.value)}
              required
            />
          </label>
          <div className="panel-actions">
            <button type="submit" className="btn btn-primary" disabled={loading}>
              {loading ? 'Generating…' : 'Generate DJ announcement'}
            </button>
          </div>
        </form>
        {error && (
          <p className="alert" role="alert">
            {error}
          </p>
        )}
        {announcement && <blockquote className="quote">{announcement}</blockquote>}
      </Setting>
    </>
  )
}
