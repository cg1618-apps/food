// Frontend: the controls a library's filter sidebar is built from.
//
// media's FilterPanel draws a row of toggle chips per filter; these are the
// same idea - buttons with aria-pressed, so a screen reader announces which
// are on - arranged as a column, because food's filters sit in a sidebar on a
// desktop and in a drawer on a phone (LibraryLayout) rather than in an inline
// panel above the list.
//
// Each library composes its own sidebar from these, since the three libraries'
// filters have different shapes: chips for a vocabulary, a switch for a
// backlog, a tree for the ingredient categories.
import { useState } from 'react'

import { cx } from '../../lib/cx'

const FOCUS_RING =
  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-1 focus-visible:ring-offset-canvas'

/** A titled group of filter controls. `hint` is a line of small print under them. */
export function FilterGroup({ title, hint, children }) {
  return (
    <fieldset className="space-y-2">
      <legend className="mb-2 font-display text-sm font-bold text-text">{title}</legend>
      {children}
      {hint ? <p className="text-xs text-text-faint">{hint}</p> : null}
    </fieldset>
  )
}

function Count({ value }) {
  if (value == null) return null
  return <span className="tabular-nums text-text-faint">{value}</span>
}

function OptionChip({ pressed, onClick, children }) {
  return (
    <button
      type="button"
      aria-pressed={pressed}
      onClick={onClick}
      className={cx(
        'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs transition-colors',
        FOCUS_RING,
        pressed
          ? 'border-brand bg-brand-soft text-brand'
          : 'border-border-strong bg-surface text-text-muted hover:border-text hover:text-text',
      )}
    >
      {children}
    </button>
  )
}

/**
 * Chips for one filter. `options` is [{ value, label, count? }] with string
 * values (the URL's); `selected` is a string for a single-valued filter or an
 * array for an "any of" one; `onToggle(value)` flips one.
 */
export function FilterOptions({ options, selected, onToggle, empty = '還沒有可選的值' }) {
  if (!options?.length) return <p className="text-xs text-text-faint">{empty}</p>
  const isOn = (value) => (Array.isArray(selected) ? selected.includes(value) : selected === value)
  return (
    <div className="flex flex-wrap gap-1.5">
      {options.map((option) => (
        <OptionChip
          key={option.value}
          pressed={isOn(option.value)}
          onClick={() => onToggle(option.value)}
        >
          {option.label}
          <Count value={option.count} />
        </OptionChip>
      ))}
    </div>
  )
}

/**
 * A switch for a filter that is on or absent - 只看待補, 只看品種. `count` is
 * shown beside the label whatever the switch's state: the stub backlog's size
 * has to be visible before anyone turns the filter on, or stubs accumulate
 * unseen (docs/frontend.md).
 */
export function FilterSwitch({ label, checked, onChange, count }) {
  return (
    <label className="flex cursor-pointer items-center gap-2 text-sm text-text">
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        className="h-4 w-4 accent-brand"
      />
      <span>{label}</span>
      {count ? (
        <span className="rounded-full bg-warn-soft px-1.5 text-xs tabular-nums text-warn">
          {count}
        </span>
      ) : null}
    </label>
  )
}

// The keys of every node above `key`, outermost first; [] when it is not in
// the tree (or is a root).
function ancestorsOf(nodes, key, path = []) {
  for (const node of nodes) {
    if (node.key === key) return path
    const found = ancestorsOf(node.children ?? [], key, [...path, node.key])
    if (found) return found
  }
  return path.length ? null : []
}

function Chevron({ open }) {
  return (
    <svg
      viewBox="0 0 12 12"
      aria-hidden="true"
      className={cx('h-3 w-3 transition-transform', open && 'rotate-90')}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M4.5 2.5 8 6l-3.5 3.5" />
    </svg>
  )
}

function TreeNode({ node, selectedKey, onSelect, open, onFlip }) {
  const hasChildren = node.children?.length > 0
  const isOpen = open.has(node.key)
  const pressed = selectedKey === node.key
  return (
    <li>
      <div className="flex items-center gap-0.5">
        {hasChildren ? (
          <button
            type="button"
            aria-expanded={isOpen}
            aria-label={`${isOpen ? '收合' : '展開'} ${node.label}`}
            onClick={() => onFlip(node.key)}
            className={cx(
              'inline-flex h-6 w-5 shrink-0 items-center justify-center rounded-sm text-text-faint hover:bg-surface-2 hover:text-text',
              FOCUS_RING,
            )}
          >
            <Chevron open={isOpen} />
          </button>
        ) : (
          <span aria-hidden="true" className="w-5 shrink-0" />
        )}
        <button
          type="button"
          aria-pressed={pressed}
          onClick={() => onSelect(node)}
          className={cx(
            'flex min-w-0 flex-1 items-center justify-between gap-2 rounded-md py-1 pr-2 pl-1 text-left text-sm transition-colors',
            FOCUS_RING,
            pressed ? 'bg-brand-soft text-brand' : 'text-text-muted hover:bg-surface-2 hover:text-text',
          )}
        >
          <span className="flex min-w-0 items-center gap-1.5">
            {/* A group is an ingredient, not a category: a ring marks it. */}
            {node.kind === 'group' ? (
              <span aria-hidden="true" className="h-1.5 w-1.5 shrink-0 rounded-full border border-current opacity-70" />
            ) : null}
            <span className="truncate">{node.label}</span>
          </span>
          <span className="tabular-nums text-xs text-text-faint">{node.count}</span>
        </button>
      </div>
      {hasChildren && isOpen ? (
        <ul className="space-y-0.5 pl-3.5">
          {node.children.map((child) => (
            <TreeNode
              key={child.key}
              node={child}
              selectedKey={selectedKey}
              onSelect={onSelect}
              open={open}
              onFlip={onFlip}
            />
          ))}
        </ul>
      ) : null}
    </li>
  )
}

/**
 * A single-choice tree whose branches open and close. `nodes` is
 * [{ key, kind?, label, count, children }]; `selectedKey` is the chosen
 * node's key or ''; `onSelect(node)` is called with the node clicked.
 *
 * Branches start closed, except the path to the chosen node, which opens
 * whenever the choice changes - a link to /ingredients?group=11 lands with
 * 肉類 and 雞肉 open, so the pressed row is on screen.
 */
export function FilterTree({ nodes, selectedKey, onSelect, empty = '還沒有分類' }) {
  const [open, setOpen] = useState(() => new Set())
  // The path is opened during render rather than in an effect, so the chosen
  // row is never drawn hidden for a frame. What is watched is the path itself,
  // not the choice alone: the tree can grow after the URL is read (the groups
  // arrive with the ingredient list, after the categories), and a path that
  // was not there yet must open when it appears. Closing a branch on the path
  // afterwards sticks, because the path has not changed.
  const path = selectedKey ? ancestorsOf(nodes ?? [], selectedKey) : null
  const watched = `${selectedKey}|${path?.join('/') ?? ''}`
  const [seen, setSeen] = useState(null)
  if (watched !== seen) {
    setSeen(watched)
    if (path?.some((key) => !open.has(key))) setOpen(new Set([...open, ...path]))
  }

  if (!nodes?.length) return <p className="text-xs text-text-faint">{empty}</p>
  const flip = (key) =>
    setOpen((current) => {
      const next = new Set(current)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  return (
    <ul className="space-y-0.5">
      {nodes.map((node) => (
        <TreeNode
          key={node.key}
          node={node}
          selectedKey={selectedKey}
          onSelect={onSelect}
          open={open}
          onFlip={flip}
        />
      ))}
    </ul>
  )
}
