import { useEffect, useState, type FormEvent } from 'react'

type Health = { app: string; db: string }

async function readError(res: Response): Promise<string> {
  try {
    const body = await res.json()
    return body.detail ?? `Request failed (${res.status})`
  } catch {
    return `Request failed (${res.status})`
  }
}

export default function App() {
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
    <main
      style={{ maxWidth: 560, margin: '2rem auto', padding: '0 1rem', fontFamily: 'sans-serif' }}
    >
      <h1>Emotion-Aware AI Radio</h1>

      <section>
        <h2>Backend status</h2>
        {healthError && <p>Backend unreachable: {healthError}</p>}
        {health && (
          <p>
            App: <strong>{health.app}</strong> · Database: <strong>{health.db}</strong>
          </p>
        )}
        {!health && !healthError && <p>Checking…</p>}
      </section>

      <section>
        <h2>DJ announcement preview</h2>
        <form onSubmit={generate} style={{ display: 'grid', gap: '0.5rem' }}>
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Title"
            required
          />
          <input
            value={artist}
            onChange={(e) => setArtist(e.target.value)}
            placeholder="Artist"
            required
          />
          <input
            value={mood}
            onChange={(e) => setMood(e.target.value)}
            placeholder="Mood"
            required
          />
          <button type="submit" disabled={loading}>
            {loading ? 'Generating…' : 'Generate DJ announcement'}
          </button>
        </form>
        {error && <p role="alert">Error: {error}</p>}
        {announcement && <blockquote>{announcement}</blockquote>}
      </section>
    </main>
  )
}
