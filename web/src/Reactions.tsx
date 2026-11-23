import { useEffect, useRef, useState, type CSSProperties } from 'react'
import { getReactions, sendReaction } from './studio.ts'

/**
 * Listener reactions: phones send an emoji, the studio screen lets it float up.
 * The screen asks for new ones every second; reactions sent before it opened are skipped.
 */

type Floating = { key: number; emoji: string; left: number; drift: number; size: number }

const POLL_MS = 1000
const LIFE_MS = 3200

export function FloatingReactions() {
  const [floating, setFloating] = useState<Floating[]>([])
  const after = useRef<number | null>(null)

  useEffect(() => {
    let alive = true
    const tick = async () => {
      try {
        const data = await getReactions(after.current ?? 0)
        if (!alive) return
        // First answer: start from now, do not replay older reactions.
        const fresh = after.current === null ? [] : data.items
        after.current = data.latest
        if (fresh.length === 0) return
        const born = fresh.slice(-12).map((r) => ({
          key: r.id,
          emoji: r.emoji,
          left: 8 + Math.random() * 84,
          drift: (Math.random() - 0.5) * 120,
          size: 44 + Math.random() * 28,
        }))
        setFloating((list) => [...list, ...born])
        window.setTimeout(() => {
          if (!alive) return
          const gone = new Set(born.map((b) => b.key))
          setFloating((list) => list.filter((f) => !gone.has(f.key)))
        }, LIFE_MS)
      } catch {
        // The screen goes on without reactions.
      }
    }
    tick()
    const id = window.setInterval(tick, POLL_MS)
    return () => {
      alive = false
      window.clearInterval(id)
    }
  }, [])

  return (
    <div className="reactions-layer" aria-hidden="true">
      {floating.map((f) => (
        <span
          key={f.key}
          className="reaction-float"
          style={
            {
              left: `${f.left}%`,
              fontSize: `${f.size}px`,
              '--drift': `${f.drift}px`,
            } as CSSProperties
          }
        >
          {f.emoji}
        </span>
      ))}
    </div>
  )
}

const PHONE_EMOJI = ['❤️', '😂', '😮', '😢', '🔥', '👏']

/** The row of emoji buttons on the phone page. */
export function ReactionBar() {
  const [sent, setSent] = useState<string | null>(null)
  const [note, setNote] = useState<string | null>(null)

  async function react(emoji: string) {
    setSent(emoji)
    try {
      await sendReaction(emoji)
      setNote(null)
    } catch {
      setNote('Easy there, one moment…')
    }
    window.setTimeout(() => setSent((s) => (s === emoji ? null : s)), 400)
  }

  return (
    <section className="reaction-bar" aria-labelledby="react-title">
      <h2 id="react-title">React to what&apos;s on air</h2>
      <div className="reaction-buttons">
        {PHONE_EMOJI.map((e) => (
          <button
            key={e}
            type="button"
            className={sent === e ? 'reaction-btn sent' : 'reaction-btn'}
            onClick={() => react(e)}
            aria-label={`Send ${e}`}
          >
            {e}
          </button>
        ))}
      </div>
      <p className="field-hint" aria-live="polite">
        {note ?? 'Your emoji floats up on the studio screen. Anonymous.'}
      </p>
    </section>
  )
}
