import { useState } from 'react'

type Props = {
  id: string
  value: string
  onChange: (value: string) => void
  autoComplete: string
  minLength?: number
  describedBy?: string
}

/** A password field with a Show/Hide button, so people can check what they typed. */
export default function PasswordInput({
  id,
  value,
  onChange,
  autoComplete,
  minLength,
  describedBy,
}: Props) {
  const [visible, setVisible] = useState(false)
  return (
    <div className="input-wrap">
      <input
        id={id}
        className="input"
        type={visible ? 'text' : 'password'}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        autoComplete={autoComplete}
        minLength={minLength}
        aria-describedby={describedBy}
        required
      />
      <button
        type="button"
        className="input-action"
        aria-controls={id}
        aria-pressed={visible}
        onClick={() => setVisible(!visible)}
      >
        {visible ? 'Hide' : 'Show'}
      </button>
    </div>
  )
}
