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

const LINK_TEXT_MAX = 40

/**
 * A link as words, for one shown without a label: host (without `www.`) and
 * path, no scheme, query or trailing slash, cut to LINK_TEXT_MAX characters
 * with an ellipsis. Null for no link; the raw text for one that does not
 * parse.
 */
export function linkText(url) {
  if (!url) return null
  let text
  try {
    const parsed = new URL(url)
    text = `${parsed.hostname.replace(/^www\./, '')}${parsed.pathname}`.replace(/\/+$/, '')
  } catch {
    return url
  }
  return text.length > LINK_TEXT_MAX ? `${text.slice(0, LINK_TEXT_MAX - 1)}…` : text
}
