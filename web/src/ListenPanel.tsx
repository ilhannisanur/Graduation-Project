import type { CSSProperties } from 'react'
import { Equalizer, type Tone } from './Banner.tsx'
import { PauseIcon, PlayIcon, SkipIcon, StopIcon } from './Icons.tsx'
import type { HistoryEntry, Radio } from './useRadio.ts'

/** The DJ's emotion picks the colour of the stage while it talks: the mood you can see. */
const EMOTION_TONES: Record<string, Tone> = {
  neutral: 'sun',
  happy: 'sun',
  excited: 'pink',
  surprised: 'pink',
  calm: 'mint',
  sad: 'sky',
  serious: 'lime',
}

function clock(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds))
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

function timeOfDay(date: Date): string {
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function Progress({ time, duration }: { time: number; duration: number }) {
  const ratio = duration > 0 ? Math.min(1, time / duration) : 0
  return (
    <div className="progress">
      <div
        className="progress-track"
        role="progressbar"
        aria-label="Time played"
        aria-valuemin={0}
        aria-valuemax={Math.round(duration)}
        aria-valuenow={Math.round(time)}
        aria-valuetext={`${clock(time)} of ${clock(duration)}`}
      >
        <div className="progress-fill" style={{ '--ratio': ratio } as CSSProperties} />
      </div>
      <div className="progress-times">
        <span>{clock(time)}</span>
        <span>{clock(duration)}</span>
      </div>
    </div>
  )
}

function Controls({ radio }: { radio: Radio }) {
  const paused = radio.status === 'paused'
  const busy = radio.status === 'loading'
  return (
    <div className="controls">
      <button
        type="button"
        className="round-btn round-btn-big"
        onClick={radio.togglePause}
        disabled={busy}
        aria-label={paused ? 'Play' : 'Pause'}
      >
        {paused ? <PlayIcon size={28} /> : <PauseIcon size={28} />}
      </button>
      <button
        type="button"
        className="round-btn"
        onClick={radio.skip}
        disabled={busy}
        aria-label="Skip to the next part"
        title="Skip"
      >
        <SkipIcon />
      </button>
      <button
        type="button"
        className="round-btn"
        onClick={radio.stop}
        aria-label="Stop the radio"
        title="Stop"
      >
        <StopIcon />
      </button>
      <label className="volume">
        <span className="sr-only">Volume</span>
        <input
          type="range"
          min={0}
          max={1}
          step={0.05}
          value={radio.volume}
          onChange={(e) => radio.setVolume(Number(e.target.value))}
        />
      </label>
    </div>
  )
}

function Stage({ radio }: { radio: Radio }) {
  const { status, current, track } = radio
  const segment = current?.segment

  if (status === 'idle' || !segment) {
    const starting = status === 'loading'
    const failed = status === 'error'
    return (
      <section className="stage tone-pink" aria-labelledby="stage-title">
        <div className="stage-body">
          <h1 id="stage-title">{failed ? 'The radio stopped' : 'Your station is ready'}</h1>
          <p className="stage-lede">
            {failed
              ? radio.error
              : 'Press start and your AI DJ takes it from here: songs picked for you, with a few words between them.'}
          </p>
          <div className="stage-actions">
            <button
              type="button"
              className="btn btn-primary btn-huge"
              onClick={failed ? radio.retry : radio.start}
              disabled={starting}
            >
              <PlayIcon size={22} />
              {starting ? 'Tuning in…' : failed ? 'Try again' : 'Start the radio'}
            </button>
          </div>
        </div>
        <Equalizer className={starting ? 'eq eq-big' : 'eq eq-big eq-still'} />
      </section>
    )
  }

  const isTrack = segment.kind === 'track'
  const tone: Tone = isTrack ? 'pink' : (EMOTION_TONES[segment.emotion] ?? 'sun')
  const live = status === 'playing'
  return (
    <section className={`stage tone-${tone}`} aria-labelledby="stage-title">
      <div className="stage-body">
        {isTrack ? (
          <>
            <p className="stage-label">
              {status === 'error'
                ? 'The radio stopped during'
                : status === 'paused'
                  ? 'Paused'
                  : 'Now playing'}
            </p>
            <h1 id="stage-title" className="stage-title">
              {segment.title}
            </h1>
            <p className="stage-artist">{segment.artist}</p>
          </>
        ) : (
          <>
            <p className="stage-label">
              Your DJ <span className="mood-chip">{segment.emotion}</span>
            </p>
            <h1 id="stage-title" className="sr-only">
              Your DJ is talking
            </h1>
            <blockquote className="stage-quote">{segment.text}</blockquote>
            {track && (
              <p className="stage-next">
                Next song: <strong>{track.title}</strong> by {track.artist}
              </p>
            )}
          </>
        )}

        {status === 'blocked' ? (
          <div className="stage-actions">
            <p>Your browser needs a tap before it plays sound.</p>
            <button type="button" className="btn btn-primary btn-huge" onClick={radio.retry}>
              <PlayIcon size={22} />
              Tap to listen
            </button>
          </div>
        ) : status === 'error' ? (
          <div className="stage-actions">
            <p className="alert" role="alert">
              {radio.error}
            </p>
            <button type="button" className="btn btn-primary" onClick={radio.retry}>
              Try again
            </button>
            <button type="button" className="btn" onClick={radio.stop}>
              Stop
            </button>
          </div>
        ) : (
          <>
            <Progress time={radio.time} duration={radio.duration} />
            <Controls radio={radio} />
            {status === 'loading' && <p className="meta">Tuning in…</p>}
          </>
        )}
      </div>
      <Equalizer className={live ? 'eq eq-big' : 'eq eq-big eq-still'} />
    </section>
  )
}

/** Title, artist, licence and source: what a Creative Commons licence asks us to show. */
function SongCredits({ radio }: { radio: Radio }) {
  const segment = radio.current?.segment
  const track = radio.track
  if (!segment || segment.kind !== 'track') {
    return (
      <p className="muted">
        {segment
          ? 'Your DJ is introducing the next song. Its credits appear here when it starts.'
          : 'Credits for each song appear here while it plays.'}
      </p>
    )
  }
  return (
    <>
      <p className="credit-line">
        “{segment.title}” by {segment.artist}
        {track ? (
          <>
            , licensed under{' '}
            <a href={track.license_url} target="_blank" rel="noreferrer">
              {track.license}
            </a>
            .
          </>
        ) : segment.license ? (
          `, licensed under ${segment.license}.`
        ) : (
          '.'
        )}
      </p>
      {track && (
        <p>
          <a className="link-arrow" href={track.source_url} target="_blank" rel="noreferrer">
            Where this song comes from
          </a>
        </p>
      )}
      {segment.reason && <p className="muted">Why this song: {segment.reason}</p>}
    </>
  )
}

function HistoryItem({ entry }: { entry: HistoryEntry }) {
  return (
    <li className={`history-item history-${entry.kind}`}>
      <span className="history-time">{timeOfDay(entry.at)}</span>
      {entry.kind === 'track' && (
        <span>
          <strong>{entry.title}</strong> <span className="muted">{entry.artist}</span>
        </span>
      )}
      {entry.kind === 'announcement' && (
        <span>
          <strong>DJ</strong> <span className="muted">({entry.emotion})</span> “{entry.text}”
        </span>
      )}
      {entry.kind === 'note' && (
        <span className="muted" title={entry.detail}>
          {entry.text}
        </span>
      )}
    </li>
  )
}

export default function ListenPanel({ radio }: { radio: Radio }) {
  const segment = radio.current?.segment
  const announcement =
    radio.status === 'error'
      ? `The radio stopped. ${radio.error ?? ''}`
      : segment && radio.status !== 'idle'
        ? segment.kind === 'track'
          ? `Now playing ${segment.title} by ${segment.artist}`
          : `Your DJ: ${segment.text}`
        : ''
  return (
    <>
      <Stage radio={radio} />
      {/* Screen readers hear each change of what is on air. */}
      <p className="sr-only" aria-live="polite">
        {announcement}
      </p>

      <div className="listen-grid">
        <section className="panel tone-pink" aria-labelledby="credits-title">
          <h2 id="credits-title" className="panel-title">
            About this song
          </h2>
          <SongCredits radio={radio} />
        </section>
        <section className="panel tone-sky" aria-labelledby="history-title">
          <h2 id="history-title" className="panel-title">
            On air so far
          </h2>
          {radio.history.length === 0 ? (
            <p className="muted">Songs and DJ intros you hear are listed here.</p>
          ) : (
            <ol className="history">
              {radio.history.map((entry) => (
                <HistoryItem key={entry.id} entry={entry} />
              ))}
            </ol>
          )}
        </section>
      </div>
    </>
  )
}
