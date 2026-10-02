// Frontend: the modal shell every dialog in the app is drawn in.
//
// media's ConfirmModal and FocusPicker shape, generalised: Escape closes, and
// the backdrop closes only on a press that both STARTS and ENDS on it - a drag
// that begins inside the dialog (selecting text in an input, moving a focus
// marker) and is released outside must not throw the dialog away.
//
// While `busy` (a delete or a merge on its way) neither Escape nor the
// backdrop closes it: the request would finish behind a dialog that is gone,
// and its answer - a refusal, a corrected count - would have nowhere to show.
//
// Focus moves into the dialog when it opens, unless a child asked for it
// with autoFocus, stays inside it - Tab from the last control goes to the
// first, Shift+Tab from the first to the last - and returns to whatever had
// it when the dialog closes.
//
// It is drawn through a portal on document.body, so a dialog opened from a
// form is never inside that <form> in the DOM: Enter in its inputs cannot
// submit the page's form, and no form-scoped CSS or validation reaches it.
// React events still bubble through the portal to the component tree, which
// is why nothing in a dialog relies on a submit event.
import { useEffect, useId, useRef } from 'react'
import { createPortal } from 'react-dom'

import { cx } from '../../lib/cx'

const WIDTHS = { sm: 'max-w-md', md: 'max-w-lg', lg: 'max-w-3xl' }

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

export default function Dialog({ title, onClose, footer, size = 'sm', busy = false, className, children }) {
  const titleId = useId()
  const panel = useRef(null)
  const pressedBackdrop = useRef(false)
  // Read during the first render, before an autoFocus child has taken focus,
  // so it is the element that opened the dialog.
  const opener = useRef(document.activeElement)

  useEffect(() => {
    function onKey(event) {
      if (event.key === 'Escape' && !busy) onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose, busy])

  useEffect(() => {
    const previous = opener.current
    if (panel.current && !panel.current.contains(document.activeElement)) {
      panel.current.focus()
    }
    return () => {
      if (previous && typeof previous.focus === 'function') previous.focus()
    }
  }, [])

  function trapTab(event) {
    if (event.key !== 'Tab' || !panel.current) return
    const focusable = [...panel.current.querySelectorAll(FOCUSABLE)]
    if (!focusable.length) {
      event.preventDefault()
      return
    }
    const first = focusable[0]
    const last = focusable.at(-1)
    const active = document.activeElement
    if (event.shiftKey && (active === first || active === panel.current)) {
      event.preventDefault()
      last.focus()
    } else if (!event.shiftKey && active === last) {
      event.preventDefault()
      first.focus()
    }
  }

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-scrim p-0 sm:items-center sm:p-4"
      onMouseDown={(event) => {
        pressedBackdrop.current = event.target === event.currentTarget
      }}
      onClick={(event) => {
        if (pressedBackdrop.current && event.target === event.currentTarget && !busy) onClose()
        pressedBackdrop.current = false
      }}
    >
      <div
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-busy={busy || undefined}
        tabIndex={-1}
        onKeyDown={trapTab}
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
    </div>,
    document.body,
  )
}
