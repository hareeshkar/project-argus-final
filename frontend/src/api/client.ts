const DEFAULT_BASE_URL = 'http://127.0.0.1:8000'

export class ApiError extends Error {
  readonly status?: number
  readonly payload?: unknown

  constructor(
    message: string,
    status?: number,
    payload?: unknown,
  ) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.payload = payload
  }
}

export const apiBaseUrl = () =>
  (import.meta.env.VITE_ARGUS_API_BASE_URL as string | undefined)?.replace(/\/$/, '') ?? DEFAULT_BASE_URL

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = init?.body
    ? {
        'Content-Type': 'application/json',
        ...init?.headers,
      }
    : init?.headers

  const response = await fetch(`${apiBaseUrl()}${path}`, {
    ...init,
    headers,
  })

  const payload = await response.json().catch(() => null)
  if (!response.ok) {
    throw new ApiError(`Argus API request failed: ${response.status}`, response.status, payload)
  }

  return payload as T
}
