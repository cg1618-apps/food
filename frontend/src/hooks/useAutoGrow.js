// Frontend: a textarea that is always as tall as its text.
//
// Media's AutoGrowTextarea fits the height the same way - collapse to `auto`,
// read scrollHeight, add the border back - and this is that, as a hook the
// shared TextArea uses, so every multi-line field in the app grows. Two
// differences, both deliberate (docs/notes/decisions.md, "Text boxes grow with
// their text"): there is no height cap, because a recipe step read through a
// scrolling slot is the thing the owner asked to be rid of; and a
// ResizeObserver re-fits on a width change, because a narrower box wraps the
// same text onto more lines.
//
// `rows` stays the minimum: once the height is `auto` the box is `rows` high,
// and scrollHeight never reports less than that.
//
// Height is set from scrollHeight rather than CSS `field-sizing: content`,
// which iOS Safari and Firefox do not reliably support.
import { useEffect, useLayoutEffect, useRef } from 'react'

export function fitHeight(el) {
  if (!el) return
  const style = window.getComputedStyle(el)
  const borders = (parseFloat(style.borderTopWidth) || 0) + (parseFloat(style.borderBottomWidth) || 0)
  const padding = (parseFloat(style.paddingTop) || 0) + (parseFloat(style.paddingBottom) || 0)
  // scrollHeight includes the padding and not the border. A border-box height
  // (Tailwind's preflight default) includes both; a content-box one neither.
  const extra = style.boxSizing === 'border-box' ? borders : -padding
  // Collapsing to `auto` shortens the page for a moment, which can pull the
  // window's scroll position up while typing near the bottom; put it back.
  const scrollY = window.scrollY
  // Collapse first, or scrollHeight never reports less than the current
  // height and the box could only grow.
  el.style.height = 'auto'
  el.style.height = `${el.scrollHeight + extra}px`
  if (window.scrollY !== scrollY) window.scrollTo(window.scrollX, scrollY)
}

// Returns the ref to put on the <textarea>. `value` is what the box holds, so
// the height follows typing, a value set from outside (a copy prefilled, a
// form reset) and the first render alike.
export function useAutoGrow(value) {
  const ref = useRef(null)

  // A layout effect, so the box is drawn at its fitted height and never
  // flashes at `rows` high first.
  useLayoutEffect(() => {
    fitHeight(ref.current)
  }, [value])

  useEffect(() => {
    const el = ref.current
    if (!el || typeof ResizeObserver === 'undefined') return undefined
    // Only a change of WIDTH re-wraps the text. Fitting changes the height,
    // which the observer also reports; re-fitting on that would be wasted
    // work and the start of a resize loop.
    let width = el.getBoundingClientRect().width
    const observer = new ResizeObserver((entries) => {
      const next = entries[entries.length - 1].contentRect.width
      if (next === width) return
      width = next
      fitHeight(el)
    })
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  return ref
}
