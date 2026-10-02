// Frontend: small display formatters the library views share.

/** A storage range in days: "3–5 天", "3 天", or null when there is none. */
export function formatDays(range) {
  if (!range) return null
  const { min, max } = range
  if (min == null && max == null) return null
  if (min == null || max == null || min === max) return `${min ?? max} 天`
  return `${min}–${max} 天`
}

/**
 * The host of a link, without `www.` - what a note's row shows instead of the
 * whole URL. Null for no link; the raw text for one that does not parse, so a
 * hand-typed address still shows something rather than nothing.
 */
export function linkHost(url) {
  if (!url) return null
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch {
    return url
  }
}
