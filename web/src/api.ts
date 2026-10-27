export type User = { id: string; username: string; created_at: string }

export type Profile = {
  genres: string[]
  artists: string[]
  languages: string[]
  news_topics: string[]
  weather_city: string | null
}

export type Option = { value: string; label: string }

export type ProfileOptions = { genres: Option[]; languages: Option[]; news_topics: Option[] }

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

type ValidationIssue = { msg: string; loc?: (string | number)[] }

function describeIssue(issue: ValidationIssue): string {
  const message = issue.msg.replace(/^Value error, /, '')
  // loc is e.g. ["body", "username"]: name the field so the user knows what to fix.
  const field = issue.loc?.[0] === 'body' ? issue.loc[1] : undefined
  if (typeof field !== 'string') return message
  const name = field.replaceAll('_', ' ')
  return `${name.charAt(0).toUpperCase()}${name.slice(1)}: ${message}`
}

export async function readError(res: Response): Promise<string> {
  try {
    const body = await res.json()
    if (Array.isArray(body.detail)) {
      // FastAPI validation errors: a list of issues, one per invalid field.
      return body.detail.map(describeIssue).join(' ')
    }
    return body.detail ?? `Request failed (${res.status})`
  } catch {
    return `Request failed (${res.status})`
  }
}

/** Calls the backend. The login cookie is sent by the browser; scripts never see it. */
export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: init.body ? { 'Content-Type': 'application/json', ...init.headers } : init.headers,
  })
  if (!res.ok) throw new ApiError(res.status, await readError(res))
  return (res.status === 204 ? undefined : await res.json()) as T
}
