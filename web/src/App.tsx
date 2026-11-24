import { useCallback, useEffect, useState } from 'react'
import { api, type User } from './api.ts'
import AuthPanel from './AuthPanel.tsx'
import Banner, { Equalizer } from './Banner.tsx'
import DevPanel from './DevPanel.tsx'
import ListenPanel from './ListenPanel.tsx'
import MiniPlayer from './MiniPlayer.tsx'
import PrivacyPanel from './PrivacyPanel.tsx'
import EmotionsPanel from './EmotionsPanel.tsx'
import ProfilePanel from './ProfilePanel.tsx'
import OnAir from './OnAir.tsx'
import RequestPage from './RequestPage.tsx'
import { useRadio } from './useRadio.ts'

const VIEWS = [
  { id: 'listen', label: 'Studio', tone: 'pink' },
  { id: 'emotions', label: 'Seven feelings', tone: 'lime' },
  { id: 'profile', label: 'Your profile', tone: 'sun' },
  { id: 'privacy', label: 'Privacy and data', tone: 'mint' },
  { id: 'dev', label: 'Developer', tone: 'sky' },
] as const

type View = (typeof VIEWS)[number]['id'] | 'request' | 'onair'

function viewFromHash(): View {
  const id = window.location.hash.replace(/^#\/?/, '')
  if (id === 'request') return 'request' // the phone page from the QR code
  if (id === 'onair') return 'onair' // the projector view
  return VIEWS.find((v) => v.id === id)?.id ?? 'listen'
}

/** The open view lives in the URL hash, so back/forward and reloads keep it. */
function useView(): View {
  const [view, setView] = useState<View>(viewFromHash)
  useEffect(() => {
    const onChange = () => setView(viewFromHash())
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])
  return view
}

export default function App() {
  // undefined: still checking whether a login cookie is valid
  const [user, setUser] = useState<User | null | undefined>(undefined)
  const view = useView()
  // Here, not in the Listen view, so the music goes on while the listener edits the profile.
  const radio = useRadio()
  const stopRadio = radio.stop

  useEffect(() => {
    api<User>('/api/me')
      .then(setUser)
      .catch(() => setUser(null))
  }, [])

  const signedOut = useCallback(() => {
    stopRadio()
    setUser(null)
  }, [stopRadio])

  async function logout() {
    stopRadio()
    try {
      await api<void>('/api/auth/logout', { method: 'POST' })
    } finally {
      setUser(null)
    }
  }

  // Phones from the QR code: no account wall and no sidebar; the page signs itself in.
  if (view === 'request') return <RequestPage />

  if (user === undefined) {
    return (
      <main className="welcome-side" style={{ minHeight: '100svh' }} aria-busy="true">
        <Equalizer />
      </main>
    )
  }

  if (user === null) {
    return (
      <main className="welcome">
        <section className="welcome-field tone-sun" aria-labelledby="welcome-title">
          <span className="wordmark">
            <Equalizer />
            Emotion-Aware AI Radio
          </span>
          <div style={{ alignSelf: 'end' }}>
            <h1 id="welcome-title">Radio that feels your mood.</h1>
            <p className="lede">
              An AI DJ picks songs for the mood of the moment and talks between them with real
              feeling. One shared broadcast, with song requests from every listener.
            </p>
          </div>
          <div style={{ display: 'flex', alignItems: 'end', justifyContent: 'space-between' }}>
            <p className="moods" aria-label="Moods the DJ plays for">
              <span className="mood">Calm</span>
              <span className="mood">Upbeat</span>
              <span className="mood">Dreamy</span>
              <span className="mood">Focused</span>
            </p>
            <Equalizer className="eq eq-big" />
          </div>
        </section>
        <div className="welcome-side">
          <AuthPanel onLoggedIn={setUser} />
          <details className="dev-tools">
            <summary>Developer tools</summary>
            <DevPanel />
          </details>
        </div>
      </main>
    )
  }

  // The projector view takes the whole screen: no top bar, no sidebar.
  if (view === 'onair') return <OnAir radio={radio} />

  const showMini = view !== 'listen' && radio.status !== 'idle' && radio.current !== null
  return (
    <>
      <header className="topbar">
        <a className="wordmark" href="#/listen">
          <Equalizer />
          Emotion-Aware AI Radio
        </a>
        <div className="account">
          <span className="muted">
            Signed in as <strong>{user.username}</strong>
          </span>
          <button type="button" className="btn" onClick={logout}>
            Sign out
          </button>
        </div>
      </header>
      <div className={showMini ? 'shell has-mini' : 'shell'}>
        <nav className="sidebar" aria-label="Sections">
          {VIEWS.map((v) => (
            <a
              key={v.id}
              className={`nav-item tone-${v.tone}`}
              href={`#/${v.id}`}
              aria-current={view === v.id ? 'page' : undefined}
            >
              {v.label}
            </a>
          ))}
        </nav>
        <main className="canvas">
          <div className="view">
            {view === 'listen' && <ListenPanel radio={radio} />}
            {view === 'emotions' && <EmotionsPanel />}
            {view === 'profile' && (
              <ProfilePanel username={user.username} onSignedOut={signedOut} />
            )}
            {view === 'privacy' && (
              <PrivacyPanel onSignedOut={signedOut} onAccountDeleted={signedOut} />
            )}
            {view === 'dev' && (
              <>
                <Banner tone="sky" title="Developer">
                  Checks for the team while the radio is being built.
                </Banner>
                <DevPanel />
              </>
            )}
          </div>
        </main>
      </div>
      {showMini && <MiniPlayer radio={radio} />}
    </>
  )
}
