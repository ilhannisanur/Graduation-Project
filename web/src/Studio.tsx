import QRCode from 'qrcode'
import { useEffect, useState } from 'react'
import MoodMap from './MoodMap.tsx'
import {
  getMap,
  getMoods,
  getQueue,
  getRequestUrl,
  getVoiceHealth,
  setMood,
  whenText,
  type MapPoint,
  type Moods,
  type QueueItem,
  type VoiceHealth,
} from './studio.ts'
import type { Radio } from './useRadio.ts'

/** Polls a loader every `ms` while the panel is on screen. */
function usePolled<T>(load: () => Promise<T>, ms: number): T | null {
  const [value, setValue] = useState<T | null>(null)
  useEffect(() => {
    let alive = true
    const tick = () =>
      load()
        .then((v) => alive && setValue(v))
        .catch(() => {})
    tick()
    const id = window.setInterval(tick, ms)
    return () => {
      alive = false
      window.clearInterval(id)
    }
  }, [load, ms])
  return value
}

function onAirIds(radio: Radio): { onAir: string | null; next: string | null } {
  const segment = radio.current?.segment
  if (!segment || radio.status === 'idle') return { onAir: null, next: null }
  if (segment.kind === 'track') return { onAir: segment.track_id, next: null }
  return { onAir: null, next: segment.introduces_track_id }
}

/** Station mood presets and the map of all songs. */
export function MoodPanel({ radio }: { radio: Radio }) {
  const [points, setPoints] = useState<MapPoint[]>([])
  const [moods, setMoods] = useState<Moods | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    getMap()
      .then(setPoints)
      .catch(() => {})
    getMoods()
      .then(setMoods)
      .catch(() => {})
  }, [])

  async function choose(id: string | null) {
    setBusy(true)
    try {
      setMoods(await setMood(id))
    } finally {
      setBusy(false)
    }
  }

  const { onAir, next } = onAirIds(radio)
  const current = moods?.current ?? null
  return (
    <section className="panel tone-lime studio-mood" aria-labelledby="mood-title">
      <div className="studio-head">
        <h2 id="mood-title" className="panel-title">
          The moment (studio control)
        </h2>
        <p className="muted">
          On air, the weather, the time and the news set the moment for everyone. Here you can play
          a moment and see the music follow it.
        </p>
        <p className="studio-now">
          {current
            ? `${current.label}: the next song will be ${current.reason}.`
            : 'No moment chosen: the DJ picks freely.'}
        </p>
      </div>
      <div className="mood-presets" role="group" aria-label="The moment">
        {moods?.presets.map((m) => (
          <button
            key={m.id}
            type="button"
            className="chip"
            aria-pressed={current?.id === m.id}
            disabled={busy}
            onClick={() => choose(current?.id === m.id ? null : m.id)}
          >
            {m.label}
          </button>
        ))}
      </div>
      <MoodMap points={points} target={current} onAirId={onAir} nextId={next} />
    </section>
  )
}

/**
 * Whether the DJ can talk right now. Without the speech service the radio keeps playing
 * songs without announcements, which is easy to miss: this says it out loud.
 */
export function VoiceStatus() {
  const health = usePolled<VoiceHealth>(getVoiceHealth, 10000)
  if (!health) return null
  const ok = health.status === 'ok' || health.status === 'degraded'
  const engine = health.primary?.engine
  const device = health.primary?.device === 'cuda' ? 'GPU' : health.primary?.device
  return (
    <p className={ok ? 'voice-status voice-ok' : 'voice-status voice-down'} role="status">
      <span className="voice-dot" aria-hidden="true" />
      {ok
        ? `DJ voice ready${engine ? `: ${engine}${device ? ` on ${device}` : ''}` : ''}`
        : 'DJ voice offline: songs play without the DJ. Start the speech service.'}
    </p>
  )
}

/** QR code for phones and the shared request queue. */
export function RequestsPanel() {
  const [url, setUrl] = useState<string | null>(null)
  const [qr, setQr] = useState<string | null>(null)
  const queue = usePolled<QueueItem[]>(getQueue, 3000)
  const [, setNow] = useState(0)

  useEffect(() => {
    getRequestUrl()
      .then(async (u) => {
        setUrl(u)
        setQr(
          await QRCode.toDataURL(u, {
            margin: 1,
            width: 360,
            color: { dark: '#17130f', light: '#ffffff' },
          }),
        )
      })
      .catch(() => {})
    const id = window.setInterval(() => setNow(Date.now()), 15000) // refresh "in N min"
    return () => window.clearInterval(id)
  }, [])

  return (
    <section className="panel tone-pink studio-requests" aria-labelledby="requests-title">
      <h2 id="requests-title" className="panel-title">
        Ask the DJ for a song
      </h2>
      <div className="request-qr">
        {qr ? (
          <img src={qr} alt={`QR code for ${url}`} width={180} height={180} />
        ) : (
          <div className="qr-placeholder" />
        )}
        <div>
          <p className="qr-lede">Scan with your phone, pick a song, leave a message.</p>
          {url && <p className="qr-url">{url.replace(/^https?:\/\//, '')}</p>}
        </div>
      </div>
      <h3 className="queue-title">In the queue</h3>
      {!queue || queue.length === 0 ? (
        <p className="muted">No requests yet. Be the first one.</p>
      ) : (
        <ol className="queue">
          {queue.map((item) => (
            <li key={item.track_id} className="queue-item">
              <span className="queue-pos">{item.position}</span>
              <span className="queue-song">
                <strong>{item.title}</strong>
                <span className="muted">{item.artist}</span>
                {item.messages.map((m) => (
                  <q key={m} className="queue-message">
                    {m}
                  </q>
                ))}
              </span>
              <span className="queue-meta">
                {item.on_air_names.length > 0 ? `for ${item.on_air_names.join(', ')}` : 'a request'}
                {item.requests > 1 && ` · ${item.requests} asked`}
                <br />
                <span className="muted">{whenText(item.estimated_play_time)}</span>
              </span>
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}
