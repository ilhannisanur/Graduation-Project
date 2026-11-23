import { useEffect, useState, type FormEvent } from 'react'
import { api, ApiError } from './api.ts'
import { Equalizer } from './Banner.tsx'
import { ReactionBar } from './Reactions.tsx'
import { whenText } from './studio.ts'

/**
 * The page phones open from the QR code on the studio screen (#/request).
 * One screen: who you are on air, which song, an optional message. A listener without an
 * account gets a private one made in the background, so asking for a song takes seconds.
 */

type Found = { id: string; title: string; artist: string }

type Sent = {
  id: string
  status: string
  estimated_play_time: string | null
  intent: { song_title: string | null; artist: string | null } | null
}

function randomHex(bytes: number): string {
  const values = crypto.getRandomValues(new Uint8Array(bytes))
  return [...values].map((b) => b.toString(16).padStart(2, '0')).join('')
}

/** Signs in with a new private account when the phone has none yet. */
async function ensureListener(): Promise<void> {
  try {
    await api('/api/me')
    return
  } catch (err) {
    if (!(err instanceof ApiError) || err.status !== 401) throw err
  }
  await api('/api/auth/register', {
    method: 'POST',
    body: JSON.stringify({
      username: `listener_${randomHex(5)}`,
      password: randomHex(16),
      preference_learning: false,
    }),
  })
}

/** Songs matching the query; results of an older query are never shown for a newer one. */
function useSearch(query: string): Found[] {
  const q = query.trim()
  const [result, setResult] = useState<{ q: string; found: Found[] }>({ q: '', found: [] })
  useEffect(() => {
    if (q.length < 2) return
    let alive = true
    const id = window.setTimeout(() => {
      api<Found[]>(`/api/tracks?q=${encodeURIComponent(q)}&limit=8`)
        .then((found) => alive && setResult({ q, found }))
        .catch(() => {})
    }, 220)
    return () => {
      alive = false
      window.clearTimeout(id)
    }
  }, [q])
  return q.length >= 2 && result.q === q ? result.found : []
}

export default function RequestPage() {
  const [name, setName] = useState('')
  const [query, setQuery] = useState('')
  const [song, setSong] = useState<Found | null>(null)
  const [message, setMessage] = useState('')
  const [readOut, setReadOut] = useState(true)
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sent, setSent] = useState<Sent | null>(null)
  const found = useSearch(song ? '' : query)

  async function send(e: FormEvent) {
    e.preventDefault()
    if (!song) return
    setSending(true)
    setError(null)
    try {
      await ensureListener()
      const text = message.trim()
      const result = await api<Sent>('/api/requests', {
        method: 'POST',
        body: JSON.stringify({
          raw_text: text || `${song.title} by ${song.artist}`,
          track_id: song.id,
          on_air_name: name.trim() || null,
          message: text || null,
          message_readout_allowed: Boolean(text) && readOut,
        }),
      })
      setSent(result)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'The radio cannot be reached right now.')
    } finally {
      setSending(false)
    }
  }

  function again() {
    setSent(null)
    setSong(null)
    setQuery('')
    setMessage('')
  }

  if (sent) {
    return (
      <main className="req-page">
        <section className="req-done tone-mint">
          <Equalizer className="eq eq-big" />
          <h1>You&apos;re on the list!</h1>
          <p className="req-song">
            <strong>{sent.intent?.song_title}</strong>
            <span>{sent.intent?.artist}</span>
          </p>
          <p className="req-when">
            {sent.estimated_play_time
              ? `It plays ${whenText(sent.estimated_play_time)}.`
              : 'The DJ will fit it in soon.'}
          </p>
          <p className="muted">Keep your ears on the studio speakers: the DJ will say it on air.</p>
          <button type="button" className="btn btn-big" onClick={again}>
            Ask for another song
          </button>
        </section>
        <ReactionBar />
      </main>
    )
  }

  return (
    <main className="req-page">
      <header className="req-head tone-pink">
        <span className="wordmark">
          <Equalizer />
          Emotion-Aware AI Radio
        </span>
        <h1>Ask the DJ for a song</h1>
        <p>Your request goes into the shared queue and the AI DJ announces it live.</p>
      </header>

      <ReactionBar />

      <form className="req-form" onSubmit={send}>
        <label className="field">
          <span>Your name on air</span>
          <input
            className="input"
            value={name}
            maxLength={40}
            autoComplete="given-name"
            placeholder="e.g. Nisa"
            onChange={(e) => setName(e.target.value)}
          />
          <span className="field-hint">Leave empty to stay anonymous.</span>
        </label>

        <div className="field">
          <span>Song</span>
          {song ? (
            <div className="req-picked">
              <span>
                <strong>{song.title}</strong>
                <span className="muted">{song.artist}</span>
              </span>
              <button type="button" className="link-btn" onClick={() => setSong(null)}>
                Change
              </button>
            </div>
          ) : (
            <>
              <input
                className="input"
                type="search"
                value={query}
                placeholder="Search by title or artist"
                onChange={(e) => setQuery(e.target.value)}
                aria-label="Search for a song"
                aria-describedby="search-hint"
              />
              <span id="search-hint" className="field-hint">
                Try “love”, “night” or “rain”. Accents don&apos;t matter.
              </span>
              {found.length > 0 && (
                <ul className="req-results" aria-label="Songs found">
                  {found.map((t) => (
                    <li key={t.id}>
                      <button type="button" onClick={() => setSong(t)}>
                        <strong>{t.title}</strong>
                        <span className="muted">{t.artist}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
        </div>

        <label className="field">
          <span>Message for the DJ (optional)</span>
          <textarea
            className="input req-message"
            value={message}
            maxLength={200}
            rows={3}
            placeholder="e.g. Good luck to everyone presenting today!"
            onChange={(e) => setMessage(e.target.value)}
          />
        </label>

        {message.trim() && (
          <label className="switch-row req-consent">
            <input
              type="checkbox"
              checked={readOut}
              onChange={(e) => setReadOut(e.target.checked)}
            />
            <span>The DJ may read my message on air</span>
          </label>
        )}

        {error && (
          <p className="alert" role="alert">
            {error}
          </p>
        )}

        <button type="submit" className="btn btn-primary btn-huge" disabled={!song || sending}>
          {sending ? 'Sending…' : 'Send my request'}
        </button>
        <p className="field-hint">
          We keep only your request, the name you typed and your message choice. See the privacy
          notice on the radio&apos;s site.
        </p>
      </form>
    </main>
  )
}
