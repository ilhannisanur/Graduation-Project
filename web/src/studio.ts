import { api } from './api.ts'

/** The studio screen's API (backend/app/api/station.py and /api/requests). */

export type Mood = {
  id: string
  label: string
  valence: number
  energy: number
  reason: string
}

export type Moods = { presets: Mood[]; current: Mood | null }

export type MapPoint = {
  id: string
  title: string
  artist: string
  valence: number
  energy: number
  tags: string[]
}

export type QueueItem = {
  position: number
  track_id: string
  title: string
  artist: string
  requests: number
  on_air_names: string[]
  /** Only messages the listeners allowed to be read on air. */
  messages: string[]
  estimated_play_time: string
}

export type VoiceHealth = {
  status: string
  primary?: { engine: string | null; device: string | null } | null
  detail?: string
}

/** Whether the DJ can speak: the speech service behind the backend. */
export const getVoiceHealth = () =>
  fetch('/api/speech/health')
    .then((res) => res.json() as Promise<VoiceHealth>)
    .catch((): VoiceHealth => ({ status: 'down' }))

export type EmotionSample = { emotion: string; label: string; text: string; file: string }

export const getMoods = () => api<Moods>('/api/station/moods')

export const setMood = (id: string | null) =>
  api<Moods>('/api/station/mood', { method: 'POST', body: JSON.stringify({ id }) })

export const getMap = () => api<MapPoint[]>('/api/station/map')

export const getQueue = () => api<QueueItem[]>('/api/requests/queue')

export const getRequestUrl = () =>
  api<{ request_url: string }>('/api/station/info').then((info) => info.request_url)

export const getEmotionSamples = () => api<EmotionSample[]>('/api/station/emotions')

// Samples can be replaced under the same file name; a new value per page load makes the
// browser fetch them again instead of playing an old copy from its cache.
const LOADED_AT = Date.now()

export const emotionAudioUrl = (file: string) =>
  `/api/station/emotions/${encodeURIComponent(file)}?v=${LOADED_AT}`

/** "in 3 min", "next", or a clock time when it is far away. */
export function whenText(iso: string, now = Date.now()): string {
  const minutes = Math.round((new Date(iso).getTime() - now) / 60000)
  if (minutes <= 1) return 'up next'
  if (minutes < 60) return `in about ${minutes} min`
  return `at ${new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`
}
