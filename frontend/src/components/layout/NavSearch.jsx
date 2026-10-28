// Frontend: the search box in the top bar - one field that finds anything.
//
// media's NavSearch is the reference: debounced, one request to /api/search
// answering a bucket per kind, a dropdown of a few rows per kind, Enter for
// the full results page. food drops media's scope menu and its gated types -
// there is no auth here and every kind is everyone's - and groups the rows
// under their kind's label (料理, 食譜 …) rather than merging them by quota:
// seven kinds of three rows each is a list a thumb can still scroll.
//
// It also stands in for media's "modify" hubs, which food does not have: the
// way to edit any entry is to find it here and use its 編輯 link on /search.
//
// Keyboard: Down and Up walk the rows across the groups, Enter opens the
// highlighted row or, with none highlighted, /search?q=…; Escape closes the
// dropdown, and a second Escape closes the phone's search row. A click
// outside closes the dropdown too.
//
// Two placements share this component (components/layout/Layout.jsx):
// `inline`, the field in the desktop bar, and `sheet`, the full-width row a
// phone opens from the search icon - it focuses itself, and calls `onDone`
// once a search has taken the reader somewhere, so the row closes behind
// them. Its input is 16px so iOS does not zoom the page on focus.
import { useEffect, useId, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { endpoints } from '../../api/endpoints'
import { useDebouncedValue } from '../../hooks/useDebouncedValue'
import { useApiQuery } from '../../hooks/useApi'
import { cx } from '../../lib/cx'
import { DROPDOWN_LIMIT, flattenGroups, groupResults, searchPath } from '../../lib/search'
import { SearchIcon } from './icons'

export default function NavSearch({ variant = 'inline', onDone, className }) {
  const sheet = variant === 'sheet'
  const navigate = useNavigate()
  const listId = useId()
  const rootRef = useRef(null)
  const [text, setText] = useState('')
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(-1)

  const term = useDebouncedValue(text.trim())
  const query = useApiQuery(
    endpoints.search.list(),
    { q: term, limit: DROPDOWN_LIMIT },
    { enabled: term !== '', staleTime: 10_000 },
  )
  // The rows on screen are the settled term's, never a half-typed one's.
  const groups = term && query.data ? groupResults(query.data.results) : []
  const flat = flattenGroups(groups)
  const showList = open && term !== '' && text.trim() !== '' && query.data !== undefined
  // A highlight past the end of a newer, shorter result set is no highlight.
  const current = active < flat.length ? active : -1

  useEffect(() => {
    function onPointer(event) {
      if (rootRef.current && !rootRef.current.contains(event.target)) setOpen(false)
    }
    document.addEventListener('mousedown', onPointer)
    return () => document.removeEventListener('mousedown', onPointer)
  }, [])

  function leaveTo(path) {
    setText('')
    setOpen(false)
    setActive(-1)
    navigate(path)
    onDone?.()
  }

  function onKeyDown(event) {
    if (event.key === 'Escape') {
      if (showList) setOpen(false)
      else onDone?.()
      return
    }
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      if (!flat.length) return
      event.preventDefault()
      setOpen(true)
      const step = event.key === 'ArrowDown' ? 1 : -1
      const next = current + step
      // -1 is "nothing highlighted", one step before the first row; the
      // walk wraps through it.
      if (next < -1) setActive(flat.length - 1)
      else if (next >= flat.length) setActive(-1)
      else setActive(next)
      return
    }
    if (event.key === 'Enter') {
      event.preventDefault()
      const chosen = showList && current >= 0 ? flat[current] : null
      if (chosen) leaveTo(chosen.type.itemTo(chosen.row.id))
      else {
        const path = searchPath(text)
        if (path) leaveTo(path)
      }
    }
  }

  const optionId = (index) => `${listId}-${index}`

  return (
    <div ref={rootRef} role="search" className={cx('relative', className)}>
      <div className="flex items-center rounded-md border border-border-strong bg-surface focus-within:border-brand focus-within:ring-2 focus-within:ring-brand/30">
        <SearchIcon className="ml-2.5 size-4 shrink-0 text-text-faint" />
        <input
          type="search"
          role="combobox"
          aria-label="搜尋全部"
          aria-expanded={showList}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={showList && current >= 0 ? optionId(current) : undefined}
          enterKeyHint="search"
          autoComplete="off"
          autoFocus={sheet}
          placeholder="搜尋料理、食譜、食材…"
          value={text}
          onChange={(event) => {
            setText(event.target.value)
            setOpen(true)
            // Typing starts over: Enter means "show me everything" until a
            // row is chosen with the arrows.
            setActive(-1)
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={onKeyDown}
          className={cx(
            'w-full min-w-0 bg-transparent px-2 text-text placeholder:text-text-faint focus:outline-none',
            sheet ? 'py-2 text-base' : 'py-1.5 text-sm',
          )}
        />
      </div>

      {showList ? (
        <div
          id={listId}
          role="listbox"
          aria-label="搜尋建議"
          className="absolute inset-x-0 top-full z-40 mt-1.5 max-h-[70dvh] overflow-y-auto overscroll-contain rounded-md border border-border bg-surface shadow-lg"
        >
          {groups.length === 0 ? (
            <p className="px-3 py-3 text-sm text-text-muted">找不到「{term}」。</p>
          ) : (
            groups.map(({ type, rows }) => (
              <div key={type.key} role="group" aria-label={type.label}>
                <div
                  aria-hidden="true"
                  className="bg-surface-2 px-3 py-1 font-display text-xs font-bold text-text-muted"
                >
                  {type.label}
                </div>
                {rows.map((row) => {
                  const entry = flat.find((item) => item.type === type && item.row === row)
                  const selected = entry.index === current
                  return (
                    <div
                      key={row.id}
                      id={optionId(entry.index)}
                      role="option"
                      aria-selected={selected}
                      // mousedown would blur the input before the click lands.
                      onMouseDown={(event) => event.preventDefault()}
                      onMouseEnter={() => setActive(entry.index)}
                      onClick={() => leaveTo(type.itemTo(row.id))}
                      className={cx(
                        'cursor-pointer px-3 py-2',
                        selected ? 'bg-brand-soft' : 'hover:bg-surface-2',
                      )}
                    >
                      <div className="truncate text-sm font-medium text-text">
                        {row.display_name}
                      </div>
                      {row.detail ? (
                        <div className="truncate text-xs text-text-faint">{row.detail}</div>
                      ) : null}
                    </div>
                  )
                })}
              </div>
            ))
          )}
          <button
            type="button"
            onMouseDown={(event) => event.preventDefault()}
            onClick={() => leaveTo(searchPath(text))}
            className="block w-full border-t border-border px-3 py-2 text-left text-sm text-brand hover:bg-surface-2"
          >
            查看全部結果
          </button>
        </div>
      ) : null}
    </div>
  )
}
