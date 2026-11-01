import { Equalizer } from './Banner.tsx'
import { PauseIcon, PlayIcon } from './Icons.tsx'
import type { Radio } from './useRadio.ts'

/** What is on air, at the foot of the other views, so the radio is never out of reach. */
export default function MiniPlayer({ radio }: { radio: Radio }) {
  const segment = radio.current?.segment
  if (radio.status === 'idle' || !segment) return null
  const paused = radio.status === 'paused' || radio.status === 'blocked'
  const label =
    segment.kind === 'track' ? `${segment.title} · ${segment.artist}` : `DJ: ${segment.text}`
  return (
    <aside className="mini-player" aria-label="Now playing">
      <Equalizer className={radio.status === 'playing' ? 'eq' : 'eq eq-still'} />
      <a className="mini-label" href="#/listen">
        {radio.status === 'error' ? 'The radio stopped. Open the player' : label}
      </a>
      <button
        type="button"
        className="round-btn"
        onClick={radio.status === 'blocked' ? radio.retry : radio.togglePause}
        disabled={radio.status === 'loading' || radio.status === 'error'}
        aria-label={paused ? 'Play' : 'Pause'}
      >
        {paused ? <PlayIcon /> : <PauseIcon />}
      </button>
    </aside>
  )
}
