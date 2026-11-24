import type { Option, Profile, ProfileOptions } from './api.ts'

/** "a", "a and b", "a, b and c" */
export function joinWords(words: string[]): string {
  if (words.length <= 1) return words.join('')
  return `${words.slice(0, -1).join(', ')} and ${words[words.length - 1]}`
}

function labels(values: string[], options: Option[]): string[] {
  return values.map((v) => options.find((o) => o.value === v)?.label ?? v)
}

/** Good morning / afternoon / evening, from the listener's own clock. */
export function greeting(date = new Date()): string {
  const hour = date.getHours()
  if (hour >= 5 && hour < 12) return 'Good morning'
  if (hour >= 12 && hour < 18) return 'Good afternoon'
  if (hour >= 18 && hour < 23) return 'Good evening'
  return 'Up late'
}

/**
 * The current (maybe unsaved) music choices in one plain sentence.
 * Only describes the settings; it does not promise a particular song.
 */
export function describeTaste(profile: Profile, options: ProfileOptions): string {
  const genres = labels(profile.genres, options.genres)
  const languages = labels(profile.languages, options.languages)

  let music = genres.length ? joinWords(genres) : 'A mix of every genre'
  if (languages.length) music += `, sung in ${joinWords(languages)}`
  return `${music}.`
}
