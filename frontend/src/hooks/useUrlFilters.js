// Frontend: a library's filters and search term, read from and written to the
// URL query. The parsing is lib/urlFilters.js; this is the react-router wiring.
//
// Two kinds of write, two kinds of history entry:
//   - a filter click PUSHES, so Back undoes it - the filtered view is a place
//     you went to;
//   - typing REPLACES, debounced, so a search for 高麗菜 is one history entry
//     and not four, and the list is not refetched per keystroke.
//
// The search box shows `search` (what is typed); the API is called with the
// URL's term, which is what `apiParams` carries.
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import {
  countActive,
  parseFilters,
  parseSearch,
  serializeFilters,
  toApiParams,
  toggleValue,
  withSearch,
} from '../lib/urlFilters'

export const SEARCH_DEBOUNCE_MS = 300

/**
 * `spec` is a module-level constant (see lib/urlFilters.js for its shape);
 * a spec built during render would change identity every render.
 *
 * Returns { values, toggle(key, value), setValue(key, value), clear(),
 * clearAll(), activeCount, search, setSearch, isFiltered, apiParams }.
 */
export function useUrlFilters(spec) {
  const [searchParams, setSearchParams] = useSearchParams()

  const values = useMemo(() => parseFilters(searchParams, spec), [searchParams, spec])
  const urlSearch = parseSearch(searchParams)

  // What the box shows runs ahead of the URL while someone types. When the URL
  // moves on its own - Back, a link - the box follows it. Adjusted during
  // render rather than in an effect, so the box never shows the old term for
  // one frame.
  const [search, setSearch] = useState(urlSearch)
  const [seenSearch, setSeenSearch] = useState(urlSearch)
  if (urlSearch !== seenSearch) {
    setSeenSearch(urlSearch)
    if (urlSearch !== search.trim()) setSearch(urlSearch)
  }

  useEffect(() => {
    if (search.trim() === urlSearch) return undefined
    const timer = setTimeout(() => {
      setSearchParams((previous) => withSearch(previous, search), { replace: true })
    }, SEARCH_DEBOUNCE_MS)
    return () => clearTimeout(timer)
  }, [search, urlSearch, setSearchParams])

  const writeValues = useCallback(
    (next) => setSearchParams((previous) => serializeFilters(next, spec, previous)),
    [setSearchParams, spec],
  )

  const toggle = useCallback(
    (key, value) => writeValues(toggleValue(values, spec, key, value)),
    [values, spec, writeValues],
  )

  const setValue = useCallback(
    (key, value) => writeValues({ ...values, [key]: value }),
    [values, writeValues],
  )

  // `clear` empties the filters and keeps the search term - the sidebar's
  // button. `clearAll` empties both - an empty result's button, where "clear"
  // means "show me everything" and a lingering term would leave it empty.
  const clear = useCallback(
    () => writeValues(parseFilters(new URLSearchParams(), spec)),
    [writeValues, spec],
  )

  const clearAll = useCallback(() => {
    setSearch('')
    setSearchParams((previous) =>
      withSearch(serializeFilters(parseFilters(new URLSearchParams(), spec), spec, previous), ''),
    )
  }, [setSearchParams, spec])

  const activeCount = countActive(values, spec)
  const apiParams = useMemo(() => toApiParams(values, spec, urlSearch), [values, spec, urlSearch])

  return {
    values,
    toggle,
    setValue,
    clear,
    clearAll,
    activeCount,
    search,
    setSearch,
    isFiltered: activeCount > 0 || urlSearch !== '',
    apiParams,
  }
}
