import type { Option, Profile, ProfileOptions } from './api.ts'

/** "a", "a and b", "a, b and c" */
export function joinWords(words: string[]): string {
  if (words.length <= 1) return words.join('')
  return `${words.slice(0, -1).join(', ')} and ${words[words.length - 1]}`
}

function labels(values: string[], options: Option[]): string[] {
  return values.map((v) => options.find((o) => o.value === v)?.label ?? v)
}

/** Splits the artists box into names, the same way the profile is saved. */
export function parseArtists(text: string): string[] {
  return text
    .split('\n')
    .map((a) => a.trim())
    .filter(Boolean)
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
 * What the current (maybe unsaved) choices would sound like, in two plain sentences.
 * Only describes the settings; it does not promise a particular song.
 */
export function describeStation(
  profile: Profile,
  artists: string[],
  options: ProfileOptions,
): [string, string] {
  const genres = labels(profile.genres, options.genres)
  const languages = labels(profile.languages, options.languages)
  const topics = labels(profile.news_topics, options.news_topics)
  const city = profile.weather_city?.trim()

  let music = genres.length ? joinWords(genres) : 'A mix of every genre'
  if (languages.length) music += `, sung in ${joinWords(languages)}`
  if (artists.length) {
    const named = artists.slice(0, 2)
    const more = artists.length - named.length
    music += `, with a nod to ${joinWords(more ? [...named, `${more} more`] : named)}`
  }

  let talk: string
  if (topics.length && city) talk = `${joinWords(topics)} news, plus the weather in ${city}.`
  else if (topics.length) talk = `${joinWords(topics)} news between songs.`
  else if (city) talk = `The weather in ${city} between songs.`
  else talk = 'No news breaks, just music.'

  return [`${music}.`, talk]
}
