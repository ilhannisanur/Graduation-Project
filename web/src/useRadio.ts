import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError, type Track } from './api.ts'
import { DUCK_LEVEL, Mixer, type Channel } from './mixer.ts'
import {
  closeSession,
  describeRadioError,
  getTrack,
  nextSegment,
  openSession,
  type NextSegment,
} from './radio.ts'

/**
 * The radio player. It plays the planner's segments (song → DJ announcement → song) like a
 * radio desk does, through the Mixer: the DJ starts over the ducked end of the song before
 * and talks over the first seconds of the song it introduces, which then fades up; two
 * songs in a row crossfade.
 * It lives in App, so the music keeps playing while the listener moves between views.
 *
 *   idle      nothing started yet, or stopped
 *   loading   asking the planner for the next segment
 *   playing   a segment is playing
 *   paused    paused by the listener
 *   blocked   the browser refused to start sound without a tap (autoplay rules)
 *   error     the radio cannot go on; `error` says why and retry() tries again
 *
 * `current` is the segment on air. While the DJ talks over a song intro it stays the
 * announcement; it becomes the song once the DJ has finished.
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

/** The song starts under the DJ this many seconds before the DJ finishes. */
const TALK_OVER_S = 2.5
/** After the DJ finishes, the ducked song comes up to full level over this long. */
const FADE_UP_S = 1.5
/** The DJ starts this many seconds before a song ends, over its ducked outro. */
const TALK_OVER_OUTRO_S = 3.5
/** How fast the ending song ducks under the DJ's first word. */
const DUCK_DOWN_S = 0.5
/** Below this much song left, an overlap is not worth it: the DJ just follows. */
const MIN_OVERLAP_S = 1
/** Two songs in a row overlap this long, one fading out and the other in. */
const CROSSFADE_S = 2
/**
 * How long before a song ends the next segment is asked for. The next block may wait a few
 * seconds for its announcement's speech, so this is generous.
 */
const PREFETCH_TRACK_S = 10
/**
 * The same before the DJ finishes. The announced song is ready on the planner at once, so
 * asking late keeps its "on air" report (requests marked played) close to when it is heard.
 */
const PREFETCH_ANNOUNCEMENT_S = TALK_OVER_S + 2

/** A segment and the channel its sound plays on. */
type Playing = { next: NextSegment; channel: Channel }
/** A /next request sent ahead of time; `value` is set once it has answered. */
type Prefetch = { promise: Promise<NextSegment>; value: NextSegment | null }

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

/** Seconds left in what a channel plays, from the file if it knows, else from the planner. */
function remaining(playing: Playing): number {
  const el = playing.channel.el
  const total =
    Number.isFinite(el.duration) && el.duration > 0 ? el.duration : playing.next.segment.duration_s
  return total - el.currentTime
}

export function useRadio(): Radio {
  // The mixer and its <audio> elements, made on first use (never during render).
  const mixerRef = useRef<Mixer | null>(null)
  const [status, setStatus] = useState<RadioStatus>('idle')
  const [error, setError] = useState<string | null>(null)
  const [current, setCurrent] = useState<NextSegment | null>(null)
  const [track, setTrack] = useState<Track | null>(null)
  const [history, setHistory] = useState<HistoryEntry[]>([])
  const [time, setTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [volume, setVolumeState] = useState(readVolume)
  const getMixer = useCallback(() => (mixerRef.current ??= new Mixer(readVolume())), [])

  const sessionRef = useRef<string | null>(null)
  // Every start, skip and stop takes a new number; answers for an older one are dropped.
  const generationRef = useRef(0)
  // The segment on air. Null while the unlock silence plays or the next one is loading,
  // so events of a channel that is not on air do not move the radio on.
  const activeRef = useRef<Playing | null>(null)
  // The announced song, already started under the DJ but not on air yet.
  const incomingRef = useRef<Playing | null>(null)
  // The song fading out under the next one in a crossfade.
  const fadingRef = useRef<Channel | null>(null)
  // The next segment, asked for before the current one ends.
  const prefetchRef = useRef<Prefetch | null>(null)
  // Whether the overlap into the next segment has begun for the segment on air.
  const overlapRef = useRef(false)
  const failuresRef = useRef(0)
  const trackIdRef = useRef<string | null>(null)
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

  const fetchNext = useCallback(async (): Promise<NextSegment> => {
    if (!sessionRef.current) sessionRef.current = await openSession()
    try {
      return await nextSegment(sessionRef.current)
    } catch (err) {
      // Sessions expire after two hours unused, or when the backend restarts: open a new one.
      if (!(err instanceof ApiError && err.status === 404)) throw err
      sessionRef.current = await openSession()
      return nextSegment(sessionRef.current)
    }
  }, [])

  const play = useCallback(async (channel: Channel, generation: number) => {
    try {
      await channel.el.play()
    } catch (err) {
      if (generation !== generationRef.current) return
      // NotAllowedError: the browser wants a tap first. Anything else shows up as an
      // "error" event on the element and is handled there.
      if (err instanceof DOMException && err.name === 'NotAllowedError') setStatus('blocked')
    }
  }, [])

  /** The channels with sound loaded right now (on air, coming in, fading out). */
  const sounding = useCallback((): Channel[] => {
    const list = [activeRef.current?.channel, incomingRef.current?.channel, fadingRef.current]
    return list.filter((c, i): c is Channel => !!c && list.indexOf(c) === i)
  }, [])

  /** A free channel for a segment: the voice for the DJ, an unused music channel for songs. */
  const channelFor = useCallback(
    (next: NextSegment): Channel => {
      const mixer = getMixer()
      if (next.segment.kind === 'announcement') return mixer.voice
      const busy = [activeRef.current?.channel, fadingRef.current]
      return mixer.music.find((c) => !busy.includes(c)) ?? mixer.music[0]
    },
    [getMixer],
  )

  /** Puts a segment on air: history, `current`, duration and the song's catalog details. */
  const record = useCallback(
    (playing: Playing) => {
      const { next } = playing
      const { segment } = next
      activeRef.current = playing
      overlapRef.current = false
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
      setTime(playing.channel.el.currentTime)

      // The announcement and its song share the details: keep them instead of reloading.
      const trackId = segment.kind === 'track' ? segment.track_id : segment.introduces_track_id
      if (trackIdRef.current !== trackId) {
        trackIdRef.current = trackId
        setTrack(null)
        void loadTrack(trackId).then((details) => {
          if (trackIdRef.current === trackId) setTrack(details)
        })
      }
    },
    [addHistory, loadTrack],
  )

  /** The DJ has finished (or was skipped): the song under it goes on air at full level. */
  const promote = useCallback(
    (incoming: Playing) => {
      incomingRef.current = null
      const before = activeRef.current
      if (before && before.channel !== incoming.channel) before.channel.silence()
      record(incoming)
      incoming.channel.fade(1, FADE_UP_S)
      if (incoming.channel.el.paused) void play(incoming.channel, generationRef.current)
      else setStatus('playing')
    },
    [record, play],
  )

  const stopFading = useCallback(() => {
    fadingRef.current?.silence()
    fadingRef.current = null
  }, [])

  const silenceAll = useCallback(() => {
    for (const channel of sounding()) channel.silence()
    activeRef.current = null
    incomingRef.current = null
    fadingRef.current = null
    overlapRef.current = false
  }, [sounding])

  /** Moves on without an overlap: skip, the end of a segment, an error, the first start. */
  const advance = useCallback(async () => {
    const generation = ++generationRef.current
    // Skipping while the DJ talks over the song intro: the song takes over now.
    const incoming = incomingRef.current
    if (incoming) {
      stopFading()
      promote(incoming)
      return
    }

    silenceAll()
    setStatus('loading')
    setError(null)
    setTime(0)

    // The planner may have handed out the next segment already; never ask past it.
    const pending = prefetchRef.current
    prefetchRef.current = null
    let next: NextSegment
    try {
      next = pending ? await pending.promise.catch(() => fetchNext()) : await fetchNext()
    } catch (err) {
      if (generation !== generationRef.current) return
      setStatus('error')
      setError(describeRadioError(err))
      return
    }
    if (generation !== generationRef.current) return

    const channel = channelFor(next)
    channel.fade(1)
    channel.el.src = next.segment.audio_url
    record({ next, channel })
    void play(channel, generation)
  }, [stopFading, promote, silenceAll, fetchNext, channelFor, record, play])

  /** Called as the segment on air plays: asks for the next one early and starts overlaps. */
  const checkAhead = useCallback(() => {
    const active = activeRef.current
    if (!active || overlapRef.current || incomingRef.current) return
    const left = remaining(active)
    const isDj = active.next.segment.kind === 'announcement'

    if (!prefetchRef.current && left <= (isDj ? PREFETCH_ANNOUNCEMENT_S : PREFETCH_TRACK_S)) {
      const promise = fetchNext()
      const prefetch: Prefetch = { promise, value: null }
      promise.then((value) => (prefetch.value = value)).catch(() => {}) // advance() retries
      prefetchRef.current = prefetch
    }

    // Not answered yet: no overlap this time, the next segment simply follows (advance()).
    const next = prefetchRef.current?.value
    if (!next) return
    const generation = generationRef.current

    // Song → DJ: the DJ starts over the end of the song, which ducks under the voice and
    // fades out by its end. The announcement is on air from the first word (subtitles).
    if (next.segment.kind === 'announcement') {
      if (isDj || left > TALK_OVER_OUTRO_S || left < MIN_OVERLAP_S) return
      prefetchRef.current = null
      stopFading()
      const old = active.channel
      old.fade(DUCK_LEVEL, DUCK_DOWN_S)
      fadingRef.current = old
      window.setTimeout(() => {
        if (fadingRef.current === old) old.fade(0, Math.max(0.3, left - DUCK_DOWN_S))
      }, DUCK_DOWN_S * 1000)
      const channel = channelFor(next)
      channel.fade(1)
      channel.el.src = next.segment.audio_url
      record({ next, channel })
      void play(channel, generation)
      return
    }

    // The DJ talks over the intro of the song it announces, which plays ducked.
    if (active.next.segment.kind === 'announcement') {
      if (left > TALK_OVER_S || next.segment.track_id !== active.next.segment.introduces_track_id)
        return
      prefetchRef.current = null
      overlapRef.current = true
      const channel = channelFor(next)
      channel.fade(DUCK_LEVEL)
      channel.el.src = next.segment.audio_url
      incomingRef.current = { next, channel }
      void play(channel, generation)
      return
    }

    // Song → song: crossfade. The new song is on air from the start of the fade.
    if (left > CROSSFADE_S) return
    prefetchRef.current = null
    stopFading()
    const old = active.channel
    const channel = channelFor(next)
    old.fade(0, CROSSFADE_S)
    fadingRef.current = old
    window.setTimeout(
      () => {
        if (fadingRef.current === old) stopFading()
      },
      CROSSFADE_S * 1000 + 300,
    )
    channel.el.src = next.segment.audio_url
    record({ next, channel })
    channel.fade(1, CROSSFADE_S, 0)
    void play(channel, generation)
  }, [fetchNext, channelFor, play, stopFading, record])

  const start = useCallback(() => {
    const mixer = getMixer()
    failuresRef.current = 0
    // Phones only allow sound that starts inside a tap. Waking the audio graph and starting
    // a short silence on every channel here, before any await, unlocks them for later.
    mixer.unlock()
    const silence = silenceUrl()
    for (const channel of mixer.channels) {
      channel.el.src = silence
      channel.el.play().catch(() => {})
    }
    void advance()
  }, [getMixer, advance])

  const stop = useCallback(() => {
    generationRef.current++
    silenceAll()
    prefetchRef.current = null
    trackIdRef.current = null
    const session = sessionRef.current
    sessionRef.current = null
    if (session) void closeSession(session)
    setStatus('idle')
    setError(null)
    setCurrent(null)
    setTrack(null)
    setTime(0)
  }, [silenceAll])

  const togglePause = useCallback(() => {
    const active = activeRef.current
    if (!active) return
    const channels = sounding()
    if (active.channel.el.paused) {
      getMixer().unlock()
      for (const channel of channels) void play(channel, generationRef.current)
    } else {
      for (const channel of channels) channel.el.pause()
    }
  }, [sounding, getMixer, play])

  const retry = useCallback(() => {
    failuresRef.current = 0
    getMixer().unlock()
    if (activeRef.current && status === 'blocked') {
      for (const channel of sounding()) void play(channel, generationRef.current)
    } else void advance()
  }, [getMixer, sounding, play, advance, status])

  const setVolume = useCallback(
    (value: number) => {
      getMixer().setVolume(value)
      setVolumeState(value)
      try {
        localStorage.setItem(VOLUME_KEY, String(value))
      } catch {
        // Remembering the volume is only a convenience.
      }
    },
    [getMixer],
  )

  // Events of the mixer's audio elements.
  useEffect(() => {
    const mixer = getMixer()
    const cleanups = mixer.channels.map((channel) => {
      const el = channel.el
      const onAir = () => activeRef.current?.channel === channel
      const isIncoming = () => incomingRef.current?.channel === channel

      const onPlaying = () => {
        if (!onAir()) return
        failuresRef.current = 0
        setStatus('playing')
      }
      const onPause = () => {
        if (onAir() && !el.ended) setStatus('paused')
      }
      const onEnded = () => {
        if (fadingRef.current === channel) stopFading()
        if (!onAir()) return
        const incoming = incomingRef.current
        if (incoming) promote(incoming)
        else void advance()
      }
      const onTime = () => {
        if (!onAir()) return
        setTime(el.currentTime)
        if (Number.isFinite(el.duration) && el.duration > 0) setDuration(el.duration)
        checkAhead()
      }
      const onError = () => {
        const failed = onAir() ? activeRef.current : isIncoming() ? incomingRef.current : null
        if (!failed) return
        failuresRef.current += 1
        const segment = failed.next.segment
        const what = segment.kind === 'track' ? `"${segment.title}"` : 'A DJ intro'
        if (failuresRef.current >= MAX_LOAD_FAILURES) {
          generationRef.current++
          silenceAll()
          prefetchRef.current = null
          setStatus('error')
          setError('Several songs in a row could not be loaded. Check that the music files exist.')
          return
        }
        addHistory({
          id: `${segment.segment_id}-failed`,
          at: new Date(),
          kind: 'note',
          text: `${what} could not be loaded, so the radio moved on`,
        })
        if (failed === incomingRef.current) {
          // The DJ goes on; the radio asks for a new segment when it finishes.
          incomingRef.current = null
          channel.silence()
        } else void advance()
      }

      el.addEventListener('playing', onPlaying)
      el.addEventListener('pause', onPause)
      el.addEventListener('ended', onEnded)
      el.addEventListener('timeupdate', onTime)
      el.addEventListener('error', onError)
      return () => {
        el.removeEventListener('playing', onPlaying)
        el.removeEventListener('pause', onPause)
        el.removeEventListener('ended', onEnded)
        el.removeEventListener('timeupdate', onTime)
        el.removeEventListener('error', onError)
      }
    })
    return () => cleanups.forEach((cleanup) => cleanup())
  }, [getMixer, advance, promote, checkAhead, stopFading, silenceAll, addHistory])

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
      mixerRef.current?.close()
      mixerRef.current = null
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
