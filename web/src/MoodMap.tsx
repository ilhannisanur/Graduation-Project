import { useMemo, useState } from 'react'
import type { MapPoint, Mood } from './studio.ts'

/**
 * Every song of the catalog on one plane: valence left to right (sad → happy), energy bottom
 * to top (calm → intense). The values come from the songs' mood tags (#75). The station's
 * mood target glows as a halo; the song on air pulses.
 */

const W = 1000
const H = 620
const PAD = 46

const x = (valence: number) => PAD + valence * (W - 2 * PAD)
const y = (energy: number) => H - PAD - energy * (H - 2 * PAD)

function quadrant(p: { valence: number; energy: number }): string {
  if (p.valence >= 0.5) return p.energy >= 0.5 ? 'q-happy' : 'q-calm'
  return p.energy >= 0.5 ? 'q-tense' : 'q-sad'
}

/** A small, stable offset per song (from its id), so songs with the same tags do not hide
 * each other. The caption still shows the exact values. */
function jitter(id: string, salt: number): number {
  let h = 2166136261 ^ salt
  for (let i = 0; i < id.length; i++) h = Math.imul(h ^ id.charCodeAt(i), 16777619)
  h = Math.imul(h ^ (h >>> 15), 2246822507 + salt)
  h ^= h >>> 13
  return ((h >>> 0) / 0xffffffff - 0.5) * 0.04
}

type Placed = MapPoint & { cx: number; cy: number }

type Props = {
  points: MapPoint[]
  target: Mood | null
  onAirId: string | null
  nextId: string | null
}

export default function MoodMap({ points, target, onAirId, nextId }: Props) {
  const [hover, setHover] = useState<MapPoint | null>(null)
  const placed = useMemo<Placed[]>(
    () =>
      points.map((p) => ({
        ...p,
        cx: x(Math.min(1, Math.max(0, p.valence + jitter(p.id, 7)))),
        cy: y(Math.min(1, Math.max(0, p.energy + jitter(p.id, 13)))),
      })),
    [points],
  )
  const byId = useMemo(() => new Map(placed.map((p) => [p.id, p])), [placed])
  const onAir = onAirId ? byId.get(onAirId) : undefined
  const next = nextId && nextId !== onAirId ? byId.get(nextId) : undefined
  const label = hover ?? onAir

  return (
    <figure className="mood-map">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label={`Mood map of ${points.length} songs: valence from sad to happy, energy from calm to intense`}
      >
        <rect
          className="map-q q-tense"
          x={PAD}
          y={PAD}
          width={(W - 2 * PAD) / 2}
          height={(H - 2 * PAD) / 2}
        />
        <rect
          className="map-q q-happy"
          x={W / 2}
          y={PAD}
          width={(W - 2 * PAD) / 2}
          height={(H - 2 * PAD) / 2}
        />
        <rect
          className="map-q q-sad"
          x={PAD}
          y={H / 2}
          width={(W - 2 * PAD) / 2}
          height={(H - 2 * PAD) / 2}
        />
        <rect
          className="map-q q-calm"
          x={W / 2}
          y={H / 2}
          width={(W - 2 * PAD) / 2}
          height={(H - 2 * PAD) / 2}
        />

        <text className="map-corner" x={PAD + 14} y={PAD + 28}>
          Tense · dark
        </text>
        <text className="map-corner" x={W - PAD - 14} y={PAD + 28} textAnchor="end">
          Happy · lively
        </text>
        <text className="map-corner" x={PAD + 14} y={H - PAD - 16}>
          Sad · slow
        </text>
        <text className="map-corner" x={W - PAD - 14} y={H - PAD - 16} textAnchor="end">
          Calm · warm
        </text>

        <text className="map-axis" x={W / 2} y={H - 12} textAnchor="middle">
          valence: sad → happy
        </text>
        <text
          className="map-axis"
          x={16}
          y={H / 2}
          textAnchor="middle"
          transform={`rotate(-90 16 ${H / 2})`}
        >
          energy: calm → intense
        </text>

        {target && (
          <g className="map-target" key={target.id}>
            <circle cx={x(target.valence)} cy={y(target.energy)} r={92} className="halo" />
            <circle cx={x(target.valence)} cy={y(target.energy)} r={92} className="halo-ring" />
            <text
              x={x(target.valence)}
              y={y(target.energy) - 102}
              textAnchor="middle"
              className="map-target-label"
            >
              {target.label}
            </text>
          </g>
        )}

        <g className="map-dots">
          {placed.map((p) => (
            <circle
              key={p.id}
              className={`dot ${quadrant(p)}`}
              cx={p.cx}
              cy={p.cy}
              r={6}
              onMouseEnter={() => setHover(p)}
              onMouseLeave={() => setHover(null)}
            >
              <title>{`${p.title} · ${p.artist}`}</title>
            </circle>
          ))}
        </g>

        {next && (
          <g className="map-next">
            <circle cx={next.cx} cy={next.cy} r={11} />
          </g>
        )}
        {onAir && (
          <g className="map-onair" key={onAir.id}>
            <circle className="pulse" cx={onAir.cx} cy={onAir.cy} r={14} />
            <circle className="core" cx={onAir.cx} cy={onAir.cy} r={11} />
          </g>
        )}
      </svg>
      <figcaption className="map-caption" aria-live="polite">
        {label ? (
          <>
            <strong>{label.title}</strong> <span className="muted">{label.artist}</span>
            <span className="map-values">
              valence {label.valence.toFixed(2)} · energy {label.energy.toFixed(2)}
              {label.tags.length > 0 && ` · ${label.tags.join(', ')}`}
            </span>
          </>
        ) : (
          <span className="muted">
            {points.length} songs, placed by their mood tags. Point at one to see it.
          </span>
        )}
      </figcaption>
    </figure>
  )
}
