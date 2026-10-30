import type { ReactNode } from 'react'

export type Tone = 'sun' | 'pink' | 'mint' | 'sky' | 'lime'

/** The radio's mark: bars that move like a level meter. Decorative only. */
export function Equalizer({ className = 'eq' }: { className?: string }) {
  return (
    <span className={className} aria-hidden="true">
      <span />
      <span />
      <span />
      <span />
      <span />
    </span>
  )
}

type Props = { tone: Tone; title: string; children: ReactNode }

/** The top of a view: its title on a whole field of the view's tone. */
export default function Banner({ tone, title, children }: Props) {
  return (
    <div className={`banner tone-${tone}`}>
      <div>
        <h1>{title}</h1>
        <p>{children}</p>
      </div>
      <Equalizer />
    </div>
  )
}
