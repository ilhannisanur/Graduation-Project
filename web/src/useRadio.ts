import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError, type Track } from './api.ts'
import {
  closeSession,
  describeRadioError,
  getTrack,
  nextSegment,
  openSession,
  type NextSegment,
} from './radio.ts'

/**
 * The radio player: one <audio> element that plays the planner's segments one after the
 * other (song → DJ announcement → song). It lives in App, so the music keeps playing while
 * the listener moves between views.
 *
 *   idle      nothing started yet, or stopped
 *   loading   asking the planner for the next segment
 *   playing   a segment is playing
 *   paused    paused by the listener
 *   blocked   the browser refused to start sound without a tap (autoplay rules)
 *   error     the radio cannot go on; `error` says why and retry() tries again
 */
export type RadioStatus = 'idle' | 'loading' | 'playing' | 'paused' | 'blocked' | 'error'

export type HistoryEntry =
  | { id: string; at: Date; kind: 'track'; title: string; artist: string }
  | { id: string; at: Date; kind: 'announcement'; text: string; emotion: string }
  | { id: string; at: Date; kind: 'note'; text: string; detail?: string }

export type Radio = {
  status: RadioStatus
  error: string | null
  current: NextSegment | null
  /** Catalog details (licence and source links) of the song playing or announced. */
  track: Track | null
  history: HistoryEntry[]
  time: number
  duration: number
  volume: number
  start: () => void
  togglePause: () => void
  skip: () => void
  stop: () => void
  retry: () => void
  setVolume: (volume: number) => void
}

/** Songs that fail to load in a row before the radio gives up instead of skipping on. */
const MAX_LOAD_FAILURES = 3
const MAX_HISTORY = 30
const VOLUME_KEY = 'radio-volume'

/** A tenth of a second of silence. Played inside the Start tap so phones allow sound later. */
function silenceUrl(): string {
  const samples = 800 // 8 kHz, 8-bit mono
  const bytes = new Uint8Array(44 + samples)
  const view = new DataView(bytes.buffer)
  const text = (offset: number, value: string) =>
    [...value].forEach((c, i) => view.setUint8(offset + i, c.charCodeAt(0)))
  text(0, 'RIFF')
  view.setUint32(4, 36 + samples, true)
  text(8, 'WAVEfmt ')
  view.setUint32(16, 16, true)
  view.setUint16(20, 1, true) // PCM
  view.setUint16(22, 1, true) // mono
  view.setUint32(24, 8000, true)
  view.setUint32(28, 8000, true)
  view.setUint16(32, 1, true)
  view.setUint16(34, 8, true)
  text(36, 'data')
  view.setUint32(40, samples, true)
  bytes.fill(128, 44) // 128 is silence for 8-bit audio
  return `data:audio/wav;base64,${btoa(String.fromCharCode(...bytes))}`
}

function readVolume(): number {
  try {
    const saved = Number(localStorage.getItem(VOLUME_KEY))
    return saved > 0 && saved <= 1 ? saved : 1
  } catch {
    return 1
  }
}

export function useRadio(): Radio {
  // The one <audio> element, made on first use (never during render).
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const getAudio = useCallback(() => (audioRef.current ??= new Audio()), [])
  const [status, setStatus] = useState<RadioStatus>('idle')
  const [error, setError] = useState<string | null>(null)
  const [current, setCurrent] = useState<NextSegment | null>(null)
  const [track, setTrack] = useState<Track | null>(null)
  const [history, setHistory] = useState<HistoryEntry[]>([])
  const [time, setTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [volume, setVolumeState] = useState(readVolume)

  const sessionRef = useRef<string | null>(null)
  // Every start, skip and stop takes a new number; answers for an older one are dropped.
  const generationRef = useRef(0)
  // The segment whose sound is loaded. Null while the unlock silence plays, so its
  // "ended" event does not move the radio on.
  const segmentRef = useRef<NextSegment | null>(null)
  const failuresRef = useRef(0)
  const tracksRef = useRef(new Map<string, Promise<Track | null>>())

  const addHistory = useCallback((entry: HistoryEntry) => {
    setHistory((list) => [entry, ...list].slice(0, MAX_HISTORY))
  }, [])

  const loadTrack = useCallback((trackId: string) => {
    let pending = tracksRef.current.get(trackId)
    if (!pending) {
      // Attribution is a nice-to-have here: a failure leaves the links out, not the song.
      pending = getTrack(trackId).catch(() => null)
      tracksRef.current.set(trackId, pending)
    }
    return pending
  }, [])

  const play = useCallback(
    async (generation: number) => {
      try {
        await getAudio().play()
      } catch (err) {
        if (generation !== generationRef.current) return
        // NotAllowedError: the browser wants a tap first. Anything else shows up as an
        // "error" event on the element and is handled there.
        if (err instanceof DOMException && err.name === 'NotAllowedError') setStatus('blocked')
      }
    },
    [getAudio],
  )

  const advance = useCallback(async () => {
    const audio = getAudio()
    const generation = ++generationRef.current
    segmentRef.current = null
    audio.pause()
    setStatus('loading')
    setError(null)
    setTime(0)

    let next: NextSegment
    try {
      if (!sessionRef.current) sessionRef.current = await openSession()
      try {
        next = await nextSegment(sessionRef.current)
      } catch (err) {
        // Sessions expire after two hours unused, or when the backend restarts: open a new one.
        if (!(err instanceof ApiError && err.status === 404)) throw err
        sessionRef.current = await openSession()
        next = await nextSegment(sessionRef.current)
      }
    } catch (err) {
      if (generation !== generationRef.current) return
      setStatus('error')
      setError(describeRadioError(err))
      return
    }
    if (generation !== generationRef.current) return

    const { segment } = next
    if (next.announcement_skipped) {
      addHistory({
        id: `${segment.segment_id}-skipped`,
        at: new Date(),
        kind: 'note',
        text: 'No DJ intro this time',
        detail: next.announcement_skipped,
      })
    }
    addHistory(
      segment.kind === 'track'
        ? {
            id: segment.segment_id,
            at: new Date(),
            kind: 'track',
            title: segment.title,
            artist: segment.artist,
          }
        : {
            id: segment.segment_id,
            at: new Date(),
            kind: 'announcement',
            text: segment.text,
            emotion: segment.emotion,
          },
    )

    setCurrent(next)
    setDuration(segment.duration_s)
    setTrack(null)
    const trackId = segment.kind === 'track' ? segment.track_id : segment.introduces_track_id
    void loadTrack(trackId).then((details) => {
      if (generation === generationRef.current) setTrack(details)
    })

    segmentRef.current = next
    audio.src = segment.audio_url
    void play(generation)
  }, [getAudio, addHistory, loadTrack, play])

  const start = useCallback(() => {
    const audio = getAudio()
    failuresRef.current = 0
    // Phones only allow sound that starts inside a tap. Starting a short silence here,
    // before any await, unlocks the element for every segment that follows.
    audio.src = silenceUrl()
    audio.play().catch(() => {})
    void advance()
  }, [getAudio, advance])

  const stop = useCallback(() => {
    const audio = getAudio()
    generationRef.current++
    segmentRef.current = null
    audio.pause()
    audio.removeAttribute('src')
    audio.load()
    const session = sessionRef.current
    sessionRef.current = null
    if (session) void closeSession(session)
    setStatus('idle')
    setError(null)
    setCurrent(null)
    setTrack(null)
    setTime(0)
  }, [getAudio])

  const togglePause = useCallback(() => {
    const audio = getAudio()
    if (!segmentRef.current) return
    if (audio.paused) void play(generationRef.current)
    else audio.pause()
  }, [getAudio, play])

  const retry = useCallback(() => {
    failuresRef.current = 0
    if (segmentRef.current && status === 'blocked') void play(generationRef.current)
    else void advance()
  }, [advance, play, status])

  const setVolume = useCallback(
    (value: number) => {
      getAudio().volume = value
      setVolumeState(value)
      try {
        localStorage.setItem(VOLUME_KEY, String(value))
      } catch {
        // Remembering the volume is only a convenience.
      }
    },
    [getAudio],
  )

  // Events of the audio element.
  useEffect(() => {
    const audio = getAudio()
    audio.preload = 'auto'
    audio.volume = volume

    const onPlaying = () => {
      if (!segmentRef.current) return
      failuresRef.current = 0
      setStatus('playing')
    }
    const onPause = () => {
      if (segmentRef.current && !audio.ended) setStatus('paused')
    }
    const onEnded = () => {
      if (segmentRef.current) void advance()
    }
    const onTime = () => {
      if (!segmentRef.current) return
      setTime(audio.currentTime)
      if (Number.isFinite(audio.duration) && audio.duration > 0) setDuration(audio.duration)
    }
    const onError = () => {
      const failed = segmentRef.current
      if (!failed) return
      failuresRef.current += 1
      const what = failed.segment.kind === 'track' ? `"${failed.segment.title}"` : 'A DJ intro'
      if (failuresRef.current >= MAX_LOAD_FAILURES) {
        generationRef.current++
        segmentRef.current = null
        setStatus('error')
        setError('Several songs in a row could not be loaded. Check that the music files exist.')
        return
      }
      addHistory({
        id: `${failed.segment.segment_id}-failed`,
        at: new Date(),
        kind: 'note',
        text: `${what} could not be loaded, so the radio moved on`,
      })
      void advance()
    }

    audio.addEventListener('playing', onPlaying)
    audio.addEventListener('pause', onPause)
    audio.addEventListener('ended', onEnded)
    audio.addEventListener('timeupdate', onTime)
    audio.addEventListener('error', onError)
    return () => {
      audio.removeEventListener('playing', onPlaying)
      audio.removeEventListener('pause', onPause)
      audio.removeEventListener('ended', onEnded)
      audio.removeEventListener('timeupdate', onTime)
      audio.removeEventListener('error', onError)
    }
    // volume is applied once here; later changes go through setVolume.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [getAudio, advance, addHistory])

  // Close the session when the tab closes, so the planner can free it at once.
  useEffect(() => {
    const onPageHide = () => {
      if (sessionRef.current) void closeSession(sessionRef.current, true)
    }
    window.addEventListener('pagehide', onPageHide)
    return () => window.removeEventListener('pagehide', onPageHide)
  }, [])

  // Phones and keyboards: title on the lock screen, play/pause and next from there.
  useEffect(() => {
    if (!('mediaSession' in navigator)) return
    const segment = current?.segment
    navigator.mediaSession.metadata = segment
      ? new MediaMetadata(
          segment.kind === 'track'
            ? { title: segment.title, artist: segment.artist, album: 'Emotion-Aware AI Radio' }
            : { title: 'Your DJ', artist: segment.text, album: 'Emotion-Aware AI Radio' },
        )
      : null
    const handlers: [MediaSessionAction, MediaSessionActionHandler | null][] = [
      ['play', segment ? togglePause : null],
      ['pause', segment ? togglePause : null],
      ['nexttrack', segment ? () => void advance() : null],
      ['stop', segment ? stop : null],
    ]
    for (const [action, handler] of handlers) {
      try {
        navigator.mediaSession.setActionHandler(action, handler)
      } catch {
        // Some browsers do not support every action.
      }
    }
  }, [current, togglePause, advance, stop])

  // The tab title says what is on air.
  useEffect(() => {
    const base = 'Emotion-Aware AI Radio'
    const segment = current?.segment
    if (!segment || status === 'idle') document.title = base
    else if (status === 'error') document.title = `Radio stopped · ${base}`
    else if (segment.kind === 'track') document.title = `${segment.title} · ${segment.artist}`
    else document.title = `DJ on air · ${base}`
  }, [current, status])

  // Stop the sound if the player is removed (for example after signing out).
  useEffect(
    () => () => {
      audioRef.current?.pause()
      if (sessionRef.current) void closeSession(sessionRef.current, true)
    },
    [],
  )

  return {
    status,
    error,
    current,
    track,
    history,
    time,
    duration,
    volume,
    start,
    togglePause,
    skip: () => void advance(),
    stop,
    retry,
    setVolume,
  }
}
