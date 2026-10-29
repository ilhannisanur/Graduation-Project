import { useEffect, useState, type FormEvent } from 'react'
import { api, ApiError, type Option, type Profile, type ProfileOptions } from './api.ts'
import Banner, { Equalizer } from './Banner.tsx'
import Setting from './Setting.tsx'
import { describeStation, greeting, parseArtists } from './station.ts'

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
      This is your profile. Tell the DJ what you love: it shapes the music, news and weather you
      hear, and you can change it any time.
    </Banner>
  )
}

/** Compares what is on screen with what was last saved. */
function snapshot(profile: Profile | null, artistsText: string): string {
  if (!profile) return ''
  return JSON.stringify({ ...profile, artists: parseArtists(artistsText) })
}

type Props = { username: string; onSignedOut: () => void }

export default function ProfilePanel({ username, onSignedOut }: Props) {
  const [options, setOptions] = useState<ProfileOptions | null>(null)
  const [profile, setProfile] = useState<Profile | null>(null)
  const [artistsText, setArtistsText] = useState('')
  const [savedSnapshot, setSavedSnapshot] = useState('')
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const dirty = profile !== null && snapshot(profile, artistsText) !== savedSnapshot

  useEffect(() => {
    Promise.all([api<ProfileOptions>('/api/profile/options'), api<Profile>('/api/me/profile')])
      .then(([loadedOptions, loadedProfile]) => {
        setOptions(loadedOptions)
        setProfile(loadedProfile)
        setArtistsText(loadedProfile.artists.join('\n'))
        setSavedSnapshot(snapshot(loadedProfile, loadedProfile.artists.join('\n')))
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
        body: JSON.stringify({ ...profile, artists: parseArtists(artistsText) }),
      })
      setProfile(saved)
      setArtistsText(saved.artists.join('\n'))
      setSavedSnapshot(snapshot(saved, saved.artists.join('\n')))
      setMessage('Saved. The DJ will use this from the next song.')
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) onSignedOut()
      else setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setSaving(false)
    }
  }

  const [musicLine, talkLine] = describeStation(profile, parseArtists(artistsText), options)
  return (
    <form onSubmit={save}>
      <Head username={username} />

      {/* Updates as the listener picks, so each choice shows what it changes. */}
      <section className="station" aria-labelledby="station-title" aria-live="polite">
        <div>
          <h2 id="station-title">On {username}&apos;s station</h2>
          <p className="station-line">{musicLine}</p>
          <p className="station-line">{talkLine}</p>
        </div>
        <Equalizer />
      </section>

      <Setting
        title="Music"
        description="What the DJ picks from. Choose as many as you like."
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
        <div className="field">
          <label htmlFor="profile-artists">Favourite artists</label>
          <textarea
            id="profile-artists"
            className="input"
            value={artistsText}
            onChange={(e) => {
              setArtistsText(e.target.value)
              setMessage(null)
            }}
            rows={4}
            aria-describedby="artists-hint"
          />
          <span id="artists-hint" className="field-hint">
            One per line.
          </span>
        </div>
      </Setting>
      <Setting
        title="News and weather"
        tone="sky"
        description="The DJ reads short updates between songs on the topics you choose."
      >
        <ChoiceGroup
          legend="News topics"
          options={options.news_topics}
          selected={profile.news_topics}
          onChange={(news_topics) => change({ news_topics })}
        />
        <label className="field">
          City for weather updates
          <input
            className="input"
            value={profile.weather_city ?? ''}
            onChange={(e) => change({ weather_city: e.target.value })}
            placeholder="e.g. Ankara"
            maxLength={100}
          />
        </label>
      </Setting>

      {/* One Save for both sections: the profile is stored as a whole. It stays in view while
          there is something to save. */}
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
