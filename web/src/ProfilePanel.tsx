import { useEffect, useState, type FormEvent } from 'react'
import { api, ApiError, type Option, type Profile, type ProfileOptions } from './api.ts'

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
    <fieldset>
      <legend>{legend}</legend>
      {options.map((option) => (
        <label key={option.value} style={{ marginRight: '0.75rem', whiteSpace: 'nowrap' }}>
          <input
            type="checkbox"
            checked={selected.includes(option.value)}
            onChange={() => toggle(option.value)}
          />{' '}
          {option.label}
        </label>
      ))}
    </fieldset>
  )
}

type Props = { onSignedOut: () => void }

export default function ProfilePanel({ onSignedOut }: Props) {
  const [options, setOptions] = useState<ProfileOptions | null>(null)
  const [profile, setProfile] = useState<Profile | null>(null)
  const [artistsText, setArtistsText] = useState('')
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([api<ProfileOptions>('/api/profile/options'), api<Profile>('/api/me/profile')])
      .then(([loadedOptions, loadedProfile]) => {
        setOptions(loadedOptions)
        setProfile(loadedProfile)
        setArtistsText(loadedProfile.artists.join('\n'))
      })
      .catch((err: Error) => {
        if (err instanceof ApiError && err.status === 401) onSignedOut()
        else setError(err.message)
      })
  }, [onSignedOut])

  if (error && !profile) return <p role="alert">Could not load your profile: {error}</p>
  if (!options || !profile) return <p>Loading your profile…</p>

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
      const artists = artistsText
        .split('\n')
        .map((a) => a.trim())
        .filter(Boolean)
      const saved = await api<Profile>('/api/me/profile', {
        method: 'PUT',
        body: JSON.stringify({ ...profile, artists }),
      })
      setProfile(saved)
      setArtistsText(saved.artists.join('\n'))
      setMessage('Saved.')
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) onSignedOut()
      else setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setSaving(false)
    }
  }

  return (
    <section>
      <h2>Your profile</h2>
      <p>You can change these at any time. They shape the music, news and weather you hear.</p>
      <form onSubmit={save} style={{ display: 'grid', gap: '0.75rem' }}>
        <ChoiceGroup
          legend="Music genres you like"
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
        <ChoiceGroup
          legend="News topics"
          options={options.news_topics}
          selected={profile.news_topics}
          onChange={(news_topics) => change({ news_topics })}
        />
        <label style={{ display: 'grid', gap: '0.25rem' }}>
          Favourite artists (one per line)
          <textarea
            value={artistsText}
            onChange={(e) => {
              setArtistsText(e.target.value)
              setMessage(null)
            }}
            rows={4}
          />
        </label>
        <label style={{ display: 'grid', gap: '0.25rem' }}>
          City for weather updates
          <input
            value={profile.weather_city ?? ''}
            onChange={(e) => change({ weather_city: e.target.value })}
            placeholder="e.g. Ankara"
            maxLength={100}
          />
        </label>
        <button type="submit" disabled={saving}>
          {saving ? 'Saving…' : 'Save profile'}
        </button>
      </form>
      {message && <p role="status">{message}</p>}
      {error && <p role="alert">Error: {error}</p>}
    </section>
  )
}
