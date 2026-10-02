// Frontend: the modal shell every dialog in the app is drawn in.
//
// media's ConfirmModal and FocusPicker shape, generalised: Escape closes, and
// the backdrop closes only on a press that both STARTS and ENDS on it - a drag
// that begins inside the dialog (selecting text in an input, moving a focus
// marker) and is released outside must not throw the dialog away.
//
// Focus moves into the dialog when it opens, unless a child asked for it
// with autoFocus, and returns to whatever had it when the dialog closes.
import { useEffect, useId, useRef } from 'react'

import { cx } from '../../lib/cx'

const WIDTHS = { sm: 'max-w-md', md: 'max-w-lg', lg: 'max-w-3xl' }

export default function Dialog({ title, onClose, footer, size = 'sm', className, children }) {
  const titleId = useId()
  const panel = useRef(null)
  const pressedBackdrop = useRef(false)
  // Read during the first render, before an autoFocus child has taken focus,
  // so it is the element that opened the dialog.
  const opener = useRef(document.activeElement)

  useEffect(() => {
    function onKey(event) {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  useEffect(() => {
    const previous = opener.current
    if (panel.current && !panel.current.contains(document.activeElement)) {
      panel.current.focus()
    }
    return () => {
      if (previous && typeof previous.focus === 'function') previous.focus()
    }
  }, [])

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-scrim p-0 sm:items-center sm:p-4"
      onMouseDown={(event) => {
        pressedBackdrop.current = event.target === event.currentTarget
      }}
      onClick={(event) => {
        if (pressedBackdrop.current && event.target === event.currentTarget) onClose()
        pressedBackdrop.current = false
      }}
    >
      <div
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        className={cx(
          'flex max-h-[90vh] w-full flex-col overflow-hidden rounded-t-lg border border-border bg-surface shadow-xl outline-none sm:rounded-lg',
          WIDTHS[size] || WIDTHS.sm,
          className,
        )}
      >
        <div className="border-b border-border px-5 py-3">
          <h2 id={titleId} className="text-lg font-bold">
            {title}
          </h2>
        </div>
        <div className="overflow-y-auto px-5 py-4 text-sm">{children}</div>
        {footer ? (
          <div className="flex flex-wrap justify-end gap-2 border-t border-border px-5 py-3">
            {footer}
          </div>
        ) : null}
      </div>
    </div>
  )
}
