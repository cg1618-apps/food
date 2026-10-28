// Frontend: the entry a URL's #anchor names, on a page read whole.
//
// 加熱 and TBD have no page per entry, so a search result opens the list at
// `#heating-12` or `#tbd-3` (lib/search.js). The browser cannot scroll there
// itself: the list arrives after the page does, and a client-side navigation
// does not move :target either. So the page asks this hook which entry is
// meant, marks it, and calls `scrollTo` once the entry is on screen.
import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'

/**
 * The anchor the URL names (without '#'), or ''. Once `ready` is true and an
 * element with that id exists, it is scrolled into view, once per anchor.
 */
export function useHashTarget(ready) {
  const { hash } = useLocation()
  const target = hash.startsWith('#') ? decodeURIComponent(hash.slice(1)) : ''

  useEffect(() => {
    if (!ready || !target) return
    const element = document.getElementById(target)
    element?.scrollIntoView?.({ block: 'center' })
  }, [ready, target])

  return target
}
