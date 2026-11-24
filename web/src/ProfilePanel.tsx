import { useEffect, useState, type FormEvent } from 'react'
import { api, ApiError, type Option, type Profile, type ProfileOptions } from './api.ts'
import Banner, { Equalizer } from './Banner.tsx'
import Setting from './Setting.tsx'
import { describeTaste, greeting } from './station.ts'

type ChoiceGroupProps = {
  legend: string
  options: Option[]
  selected: string[]
  onChange: (selected: string[]) => void
}

function ChoiceGroup({ legend, options, selected, onChange }: ChoiceGroupProps) {
  function toggle(value: string) {
    onChange(selected.includes(value) ? selected.filter((v) => v !== value) : [...selected, value])
  }
  return (
    <fieldset className="field">
      <legend>{legend}</legend>
      <div className="chips">
        {options.map((option) => (
          <label key={option.value} className="chip">
            <input
              type="checkbox"
              checked={selected.includes(option.value)}
              onChange={() => toggle(option.value)}
            />
            {option.label}
          </label>
        ))}
      </div>
    </fieldset>
  )
}

function Head({ username }: { username: string }) {
  return (
    <Banner tone="sun" title={`${greeting()}, ${username}`}>
      This is your profile. The broadcast is shared: your taste joins everyone else&apos;s when the
      DJ picks songs. You can change it any time.
    </Banner>
  )
}

/** Compares what is on screen with what was last saved. */
function snapshot(profile: Profile | null): string {
  return profile ? JSON.stringify(profile) : ''
}

type Props = { username: string; onSignedOut: () => void }

export default function ProfilePanel({ username, onSignedOut }: Props) {
  const [options, setOptions] = useState<ProfileOptions | null>(null)
  const [profile, setProfile] = useState<Profile | null>(null)
  const [savedSnapshot, setSavedSnapshot] = useState('')
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const dirty = profile !== null && snapshot(profile) !== savedSnapshot

  useEffect(() => {
    Promise.all([api<ProfileOptions>('/api/profile/options'), api<Profile>('/api/me/profile')])
      .then(([loadedOptions, loadedProfile]) => {
        setOptions(loadedOptions)
        setProfile(loadedProfile)
        setSavedSnapshot(snapshot(loadedProfile))
      })
      .catch((err: Error) => {
        if (err instanceof ApiError && err.status === 401) onSignedOut()
        else setError(err.message)
      })
  }, [onSignedOut])

  // The browser asks before closing or reloading the tab while choices are unsaved.
  useEffect(() => {
    if (!dirty) return
    const warn = (e: BeforeUnloadEvent) => e.preventDefault()
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [dirty])

  if (error && !profile) {
    return (
      <>
        <Head username={username} />
        <p className="alert" role="alert" style={{ marginTop: 32 }}>
          Could not load your profile: {error}
        </p>
      </>
    )
  }
  if (!options || !profile) {
    return (
      <>
        <Head username={username} />
        <p className="muted" style={{ marginTop: 32 }} aria-busy="true">
          Loading your profile…
        </p>
      </>
    )
  }

  function change(patch: Partial<Profile>) {
    setProfile((current) => (current ? { ...current, ...patch } : current))
    setMessage(null)
  }

  async function save(e: FormEvent) {
    e.preventDefault()
    if (!profile) return
    setSaving(true)
    setError(null)
    setMessage(null)
    try {
      const saved = await api<Profile>('/api/me/profile', {
        method: 'PUT',
        body: JSON.stringify(profile),
      })
      setProfile(saved)
      setSavedSnapshot(snapshot(saved))
      setMessage('Saved.')
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) onSignedOut()
      else setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={save}>
      <Head username={username} />

      {/* Updates as the listener picks, so each choice shows what it changes. */}
      <section className="station" aria-labelledby="station-title" aria-live="polite">
        <div>
          <h2 id="station-title">{username}&apos;s taste</h2>
          <p className="station-line">{describeTaste(profile, options)}</p>
        </div>
        <Equalizer />
      </section>

      <Setting
        title="Music"
        description="One shared broadcast for everyone: the tastes of the listeners help the DJ choose between songs that fit the moment. Choose as many as you like."
        tone="pink"
      >
        <ChoiceGroup
          legend="Genres you like"
          options={options.genres}
          selected={profile.genres}
          onChange={(genres) => change({ genres })}
        />
        <ChoiceGroup
          legend="Song languages"
          options={options.languages}
          selected={profile.languages}
          onChange={(languages) => change({ languages })}
        />
      </Setting>

      {/* The profile is stored as a whole. The bar stays in view while there is something to
          save. */}
      <div className={dirty ? 'form-actions save-bar is-dirty' : 'form-actions save-bar'}>
        {error && (
          <p className="alert" role="alert">
            {error}
          </p>
        )}
        <span className="status" role="status">
          {dirty ? 'You have unsaved changes.' : message}
        </span>
        <button type="submit" className="btn btn-primary btn-big" disabled={saving || !dirty}>
          {saving ? 'Saving…' : 'Save profile'}
        </button>
      </div>
    </form>
  )
}
