import { api, ApiError, type Track } from './api.ts'

/**
 * The broadcast planner's API (#9, docs/m1-entegrasyon.md "Oynatıcı için sözleşme"):
 * open a session, ask for the next segment whenever one ends, close it when done.
 */

export type TrackSegment = {
  kind: 'track'
  segment_id: string
  track_id: string
  title: string
  artist: string
  license: string | null
  reason: string | null
  duration_s: number
  audio_url: string
}

export type AnnouncementSegment = {
  kind: 'announcement'
  segment_id: string
  text: string
  emotion: string
  duration_s: number
  audio_url: string
  introduces_track_id: string
}

export type Segment = TrackSegment | AnnouncementSegment

export type NextSegment = {
  session_id: string
  position: number
  segment: Segment
  announcement_skipped: string | null
}

type SessionCreated = { session_id: string; user_id: string }

export async function openSession(): Promise<string> {
  const created = await api<SessionCreated>('/api/sessions', { method: 'POST' })
  return created.session_id
}

export function nextSegment(sessionId: string): Promise<NextSegment> {
  return api<NextSegment>(`/api/sessions/${encodeURIComponent(sessionId)}/next`)
}

/** Closes the session. `keepalive` lets the request finish while the page is closing. */
export async function closeSession(sessionId: string, keepalive = false): Promise<void> {
  try {
    await fetch(`/api/sessions/${encodeURIComponent(sessionId)}`, {
      method: 'DELETE',
      keepalive,
    })
  } catch {
    // Not fatal: the planner removes unused sessions by itself after two hours.
  }
}

/** Licence and source links of a song, for the attribution under "Now playing". */
export function getTrack(trackId: string): Promise<Track> {
  return api<Track>(`/api/tracks/${encodeURIComponent(trackId)}`)
}

/** What went wrong, in words for the listener, and whether trying again can help. */
export function describeRadioError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 503) {
      return 'No song is available right now. The music catalog may be empty or the database may be down.'
    }
    if (err.status === 404) return 'Your listening session has expired.'
    // 502/504 come from the dev proxy when the backend is not running.
    if (err.status === 502 || err.status === 504) return UNREACHABLE
    if (err.status >= 500) return 'The radio server ran into a problem. Try again in a moment.'
    return err.message
  }
  // fetch() rejects with a TypeError when the server cannot be reached at all.
  return UNREACHABLE
}

const UNREACHABLE = 'The radio server cannot be reached. Check that the backend is running.'
