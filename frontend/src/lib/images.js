// Frontend: focal points for cropped images.
//
// media's lib/covers.js focus helpers, carried over unchanged in behaviour.
// Almost every image here is drawn cropped (object-cover) - a cover in a
// grid, a hero, a thumbnail - and a crop keeps the centre unless told
// otherwise. An attachment's `focus` is "X% Y%", the CSS object-position that
// keeps the subject in frame; null is centred. The backend validates the same
// shape (app/schemas, after media's image_focus.py).
//
// focus-images.test.js is what makes every cropped image tag use this.

/** The inline style that applies a focal point; undefined when centred. */
export function focusStyle(focus) {
  return focus ? { objectPosition: focus } : undefined
}

const CENTRE = Object.freeze({ x: 50, y: 50 })
const FOCUS_PATTERN = /^\s*(\d{1,3})%\s+(\d{1,3})%\s*$/

function clampPercent(n) {
  return Math.min(100, Math.max(0, Math.round(n)))
}

/** "X% Y%" -> { x, y }; anything else (null, "", malformed) is the centre. */
export function parseFocus(focus) {
  const match = typeof focus === 'string' ? FOCUS_PATTERN.exec(focus) : null
  if (!match) return CENTRE
  return { x: clampPercent(Number(match[1])), y: clampPercent(Number(match[2])) }
}

/**
 * { x, y } -> "X% Y%", clamped to whole percentages in 0..100. The centre is
 * null rather than "50% 50%": a centred image stores no focus at all.
 */
export function formatFocus({ x, y }) {
  const cx = clampPercent(x)
  const cy = clampPercent(y)
  if (cx === CENTRE.x && cy === CENTRE.y) return null
  return `${cx}% ${cy}%`
}
