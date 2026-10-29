import { useId, type ReactNode } from 'react'
import type { Tone } from './Banner.tsx'

type Props = {
  title: string
  description?: ReactNode
  /** Colours the section's dot, the choices picked in it and its switch. */
  tone?: Tone
  children: ReactNode
}

/** One settings row: a title and a short description beside the panel that holds the controls. */
export default function Setting({ title, description, tone, children }: Props) {
  const id = useId()
  return (
    <section className={tone ? `setting tone-${tone}` : 'setting'} aria-labelledby={id}>
      <div className="setting-label">
        <h2 id={id}>{title}</h2>
        {description && <p>{description}</p>}
      </div>
      <div className="panel">{children}</div>
    </section>
  )
}
