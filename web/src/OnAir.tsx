import QRCode from 'qrcode'
import { useEffect, useState } from 'react'
import { Equalizer, type Tone } from './Banner.tsx'
import { PlayIcon } from './Icons.tsx'
import { EMOTION_TONES, Subtitles } from './ListenPanel.tsx'
import MoodMap from './MoodMap.tsx'
import { FloatingReactions } from './Reactions.tsx'
import {
  getMap,
  getMoods,
  getQueue,
  getRequestUrl,
  whenText,
  type MapPoint,
  type Mood,
  type QueueItem,
} from './studio.ts'
import type { Radio } from './useRadio.ts'

/**
 * The projector view (#/onair): what is on air, big enough to read from the back of a
 * classroom, with the QR code, the queue and the mood map on the side. Keys for the
 * presenter: Space pauses, → skips, Esc goes back to the studio.
 */

function clockNow(): string {
  return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function useClock(): string {
  const [now, setNow] = useState(clockNow)
  useEffect(() => {
    const id = window.setInterval(() => setNow(clockNow()), 10000)
    return () => window.clearInterval(id)
  }, [])
  return now
}

function useSidebarData() {
  const [queue, setQueue] = useState<QueueItem[]>([])
  const [moment, setMoment] = useState<Mood | null>(null)
  const [points, setPoints] = useState<MapPoint[]>([])
  const [url, setUrl] = useState<string | null>(null)
  const [qr, setQr] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    getMap()
      .then((p) => alive && setPoints(p))
      .catch(() => {})
    getRequestUrl()
      .then(async (u) => {
        if (!alive) return
        setUrl(u)
        const code = await QRCode.toDataURL(u, { margin: 1, width: 420 })
        if (alive) setQr(code)
      })
      .catch(() => {})
    const tick = () => {
      getQueue()
        .then((q) => alive && setQueue(q))
        .catch(() => {})
      getMoods()
        .then((m) => alive && setMoment(m.current))
        .catch(() => {})
    }
    tick()
    const id = window.setInterval(tick, 3000)
    return () => {
      alive = false
      window.clearInterval(id)
    }
  }, [])

  return { queue, moment, points, url, qr }
}

function leave() {
  if (document.fullscreenElement) document.exitFullscreen().catch(() => {})
  window.location.hash = '#/listen'
}

export default function OnAir({ radio }: { radio: Radio }) {
  const clock = useClock()
  const { queue, moment, points, url, qr } = useSidebarData()
  const { status, current, time, duration } = radio
  const segment = status === 'idle' ? undefined : current?.segment
  const { togglePause, skip } = radio

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement) return
      if (e.key === 'Escape') leave()
      else if (e.key === 'ArrowRight') skip()
      else if (e.key === ' ') {
        e.preventDefault()
        togglePause()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [togglePause, skip])

  const tone: Tone = !segment
    ? 'sun'
    : segment.kind === 'track'
      ? 'pink'
      : (EMOTION_TONES[segment.emotion] ?? 'sun')
  const ratio = duration > 0 ? Math.min(1, time / duration) : 0
  const onAirId = segment?.kind === 'track' ? segment.track_id : null
  const nextId = segment?.kind === 'announcement' ? segment.introduces_track_id : null

  return (
    <div className={`onair tone-${tone}`}>
      <FloatingReactions />

      <main className="onair-main">
        <header className="onair-top">
          <span className="onair-live">
            <span className="onair-dot" aria-hidden="true" />
            {status === 'paused' ? 'Paused' : 'On air'}
          </span>
          <span className="onair-brand">
            <Equalizer />
            Emotion-Aware AI Radio
          </span>
          <span className="onair-clock">{clock}</span>
        </header>

        <section className="onair-stage" aria-live="polite">
          {!segment && (
            <>
              <h1 className="onair-title">The station is ready.</h1>
              <button type="button" className="btn btn-primary btn-huge" onClick={radio.start}>
                <PlayIcon size={22} />
                Start the radio
              </button>
            </>
          )}

          {segment?.kind === 'announcement' && (
            <>
              <p className="onair-label">
                Your DJ <span className="onair-chip">{segment.emotion}</span>
              </p>
              <Subtitles text={segment.text} time={time} duration={duration} />
            </>
          )}

          {segment?.kind === 'track' && (
            <>
              {segment.requested_by ? (
                <p className="onair-chip onair-request">
                  {segment.requested_by.length > 0
                    ? `Requested by ${segment.requested_by.join(', ')}`
                    : 'A listener request'}
                </p>
              ) : (
                <p className="onair-label">Now playing</p>
              )}
              <h1 className="onair-title">{segment.title}</h1>
              <p className="onair-artist">{segment.artist}</p>
              {segment.request_messages?.map((m) => (
                <q key={m} className="onair-message">
                  {m}
                </q>
              ))}
              {segment.reason && !segment.requested_by && (
                <p className="onair-why">Why this song: {segment.reason.toLowerCase()}</p>
              )}
            </>
          )}
        </section>

        {segment && (
          <div className="onair-progress" aria-hidden="true">
            <div style={{ width: `${ratio * 100}%` }} />
          </div>
        )}
        <p className="onair-keys">Space pause · → skip · Esc back to the studio</p>
      </main>

      <aside className="onair-side">
        <div className="onair-qr">
          {qr ? <img src={qr} alt={`QR code for ${url}`} /> : <div className="qr-placeholder" />}
          <div>
            <p className="onair-side-title">Ask the DJ for a song</p>
            <p className="onair-side-text">Scan, pick a song, leave a message, send an emoji.</p>
          </div>
        </div>

        <div className="onair-queue">
          <p className="onair-side-title">Up next from listeners</p>
          {queue.length === 0 ? (
            <p className="onair-side-text">No requests yet. Be the first one.</p>
          ) : (
            <ol>
              {queue.slice(0, 4).map((item) => (
                <li key={item.track_id}>
                  <strong>{item.title}</strong>
                  <span>
                    {item.on_air_names.length > 0 ? `for ${item.on_air_names.join(', ')} · ` : ''}
                    {whenText(item.estimated_play_time)}
                  </span>
                </li>
              ))}
            </ol>
          )}
        </div>

        <div className="onair-map">
          <p className="onair-side-title">
            {moment ? `The moment: ${moment.label}` : 'The mood map'}
          </p>
          <MoodMap points={points} target={moment} onAirId={onAirId} nextId={nextId} />
        </div>
      </aside>

      <button type="button" className="onair-exit" onClick={leave}>
        Back to studio
      </button>
    </div>
  )
}

/** Opens the projector view, full screen when the browser allows it. */
export function openOnAir() {
  document.documentElement.requestFullscreen?.().catch(() => {})
  window.location.hash = '#/onair'
}
