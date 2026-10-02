// Frontend: a library's filters and search term, as a URL query.
//
// media holds library filters in component state. food keeps them in the URL,
// because the spec needs two things state cannot give: a filtered view that
// can be bookmarked, and links INTO a filtered view - the ingredient page's
// category link is `/ingredients?category=3`, and a library that ignored the
// query was a known defect. See docs/notes/decisions.md.
//
// A library declares a SPEC: one entry per URL key,
//
//   { [urlKey]: { type: 'single' | 'multi' | 'bool', api: 'query_param' } }
//
//   single - one value or none (`?category=3`); a string, '' when absent;
//   multi  - any of several (`?course=1&course=2`); an array of strings;
//   bool   - a switch that is on or absent (`?stub=1`); true or false. Off is
//            the ABSENCE of the filter, never `false`: `needs_detail=false`
//            would mean "only the finished ones", a different filter.
//
// `id: true` on a single or multi key whose API parameter is an integer id
// keeps only whole numbers: a hand-edited `?category=abc` is ignored rather
// than sent, where the API would refuse the whole list with a 422.
//
// The search term is the reserved key `q`, outside the spec, and is passed to
// the API as `q`. The URL keys are short and readable rather than the API's
// `_id` names, because a person reads and edits them.
//
// Everything here is pure, so the hook that wires it to react-router is thin
// and the parsing is tested without a router.

export const SEARCH_KEY = 'q'

/** The URL query -> one value per spec key, each of its type's shape. */
const ID = /^\d+$/

export function parseFilters(searchParams, spec) {
  const values = {}
  for (const [key, def] of Object.entries(spec)) {
    const valid = (value) => Boolean(value) && (!def.id || ID.test(value))
    if (def.type === 'multi') {
      // Repeated keys, de-duplicated, blanks dropped: a hand-edited
      // `?course=&course=2` means course 2.
      values[key] = [...new Set(searchParams.getAll(key).filter(valid))]
    } else if (def.type === 'bool') {
      const raw = searchParams.get(key)
      values[key] = raw !== null && raw !== '' && raw !== '0' && raw !== 'false'
    } else {
      const value = searchParams.get(key) ?? ''
      values[key] = valid(value) ? value : ''
    }
  }
  return values
}

/**
 * Write `values` into a copy of `searchParams`. Keys outside the spec (the
 * search term among them) are kept; each spec key is rewritten from scratch,
 * so an emptied filter leaves the URL rather than lingering as `?label=`.
 */
export function serializeFilters(values, spec, searchParams = new URLSearchParams()) {
  const next = new URLSearchParams(searchParams)
  for (const [key, def] of Object.entries(spec)) {
    next.delete(key)
    const value = values[key]
    if (def.type === 'multi') {
      for (const item of value ?? []) if (item) next.append(key, item)
    } else if (def.type === 'bool') {
      if (value) next.set(key, '1')
    } else if (value) {
      next.set(key, value)
    }
  }
  return next
}

/** The search term in the URL, '' when there is none. */
export function parseSearch(searchParams) {
  return searchParams.get(SEARCH_KEY) ?? ''
}

/** A copy of `searchParams` carrying `term`, trimmed; blank removes it. */
export function withSearch(searchParams, term) {
  const next = new URLSearchParams(searchParams)
  const trimmed = (term ?? '').trim()
  if (trimmed) next.set(SEARCH_KEY, trimmed)
  else next.delete(SEARCH_KEY)
  return next
}

/** How many filters are on - the number on the 篩選 button. The search term is not a filter. */
export function countActive(values, spec) {
  let count = 0
  for (const [key, def] of Object.entries(spec)) {
    const value = values[key]
    if (def.type === 'multi') count += value?.length ?? 0
    else if (value) count += 1
  }
  return count
}

/** `values` with `value` added to or removed from a multi key, or a single key set or cleared. */
export function toggleValue(values, spec, key, value) {
  const def = spec[key]
  if (def.type === 'multi') {
    const current = values[key] ?? []
    return {
      ...values,
      [key]: current.includes(value) ? current.filter((v) => v !== value) : [...current, value],
    }
  }
  if (def.type === 'bool') return { ...values, [key]: !values[key] }
  // A single choice clicked again is cleared, as a radio with a way back.
  return { ...values, [key]: values[key] === value ? '' : value }
}

/**
 * The parameters for the list endpoint: each key renamed to its `api` name,
 * a multi as an array (buildUrl repeats the key), a bool as `true` only when
 * on. Empty values are dropped so the cache key does not grow `null`s.
 */
export function toApiParams(values, spec, search = '') {
  const params = {}
  if (search.trim()) params.q = search.trim()
  for (const [key, def] of Object.entries(spec)) {
    const value = values[key]
    const name = def.api ?? key
    if (def.type === 'multi') {
      if (value?.length) params[name] = value
    } else if (def.type === 'bool') {
      if (value) params[name] = true
    } else if (value) {
      params[name] = value
    }
  }
  return params
}
