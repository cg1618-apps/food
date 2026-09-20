// The only file in this application that calls fetch().
//
// Everything else goes through these helpers, so that the two things every
// caller needs - a readable message and the status code - are produced in one
// place rather than approximated in twelve.
//
// Both fixes below are defects live in media's equivalent wrapper, and both are
// the kind that only appear on the failure path:
//
//   FastAPI's automatic validation error puts an ARRAY under `detail`, unlike
//   every hand-raised error in the app. `new Error(array)` stringifies to
//   "[object Object]", and a malformed body is exactly what produces it - so
//   the one message users actually hit is the one that renders as noise.
//
//   Throwing a bare Error discards the status. Callers that need one then
//   re-implement fetch by hand, and a documented 409 contract becomes
//   unreachable without anything saying so.

export function buildUrl(url, params) {
  if (!params) return url
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '') continue
    search.append(key, String(value))
  }
  const query = search.toString()
  return query ? `${url}?${query}` : url
}

export function errorMessage(body, fallback) {
  const detail = body?.detail
  if (Array.isArray(detail)) {
    // FastAPI validation errors: {loc, msg, type} per entry. The last element
    // of `loc` is the field name; the rest is request plumbing nobody reads.
    return (
      detail
        .map((entry) => {
          const field = Array.isArray(entry?.loc) ? entry.loc.at(-1) : null
          return field ? `${field}: ${entry.msg}` : entry?.msg
        })
        .filter(Boolean)
        .join('; ') || fallback
    )
  }
  if (typeof detail === 'string' && detail) return detail
  if (typeof body?.message === 'string' && body.message) return body.message
  return fallback
}

export async function fetchJson(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
  })

  if (response.status === 204) return null

  let body = null
  try {
    body = await response.json()
  } catch {
    body = null
  }

  if (!response.ok) {
    const error = new Error(errorMessage(body, response.statusText))
    // The whole point: a caller may branch on 409 without re-implementing
    // fetch, and the extras ride along so a dialog can correct itself in place
    // instead of asking for a reload.
    error.status = response.status
    error.body = body
    throw error
  }

  return body
}

export function jsonBody(body) {
  return { body: JSON.stringify(body) }
}
