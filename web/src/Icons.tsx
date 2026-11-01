import type { ReactNode } from 'react'

/** Small player icons, drawn in the current text colour. Decorative: buttons carry the label. */

type Props = { size?: number }

function Svg({ size = 20, children }: Props & { children: ReactNode }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      {children}
    </svg>
  )
}

export function PlayIcon(props: Props) {
  return (
    <Svg {...props}>
      <path d="M8 5.5v13a1 1 0 0 0 1.5.86l10.5-6.5a1 1 0 0 0 0-1.72L9.5 4.64A1 1 0 0 0 8 5.5Z" />
    </Svg>
  )
}

export function PauseIcon(props: Props) {
  return (
    <Svg {...props}>
      <rect x="6" y="5" width="4.5" height="14" rx="1.5" />
      <rect x="13.5" y="5" width="4.5" height="14" rx="1.5" />
    </Svg>
  )
}

export function SkipIcon(props: Props) {
  return (
    <Svg {...props}>
      <path d="M5 6.2v11.6a1 1 0 0 0 1.55.83L15 13v4.8a1 1 0 0 0 2 0V6.2a1 1 0 0 0-2 0V11L6.55 5.37A1 1 0 0 0 5 6.2Z" />
    </Svg>
  )
}

export function StopIcon(props: Props) {
  return (
    <Svg {...props}>
      <rect x="6" y="6" width="12" height="12" rx="2" />
    </Svg>
  )
}
