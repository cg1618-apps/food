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
import { cx } from '../../lib/cx'
import { flatten } from '../../lib/tree'

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

/**
 * The category tree as a single-choice list, indented by depth, each node
 * with its own ingredient count. Choosing a node filters to ingredients filed
 * under THAT node exactly (the API's `category_id`), and the count beside it
 * is the same number, so the two cannot disagree.
 */
export function FilterTree({ nodes, selected, onToggle }) {
  const rows = flatten(nodes ?? [])
  if (!rows.length) return <p className="text-xs text-text-faint">還沒有分類</p>
  return (
    <ul className="space-y-0.5">
      {rows.map((node) => {
        const value = String(node.id)
        const pressed = selected === value
        return (
          <li key={node.id}>
            <button
              type="button"
              aria-pressed={pressed}
              onClick={() => onToggle(value)}
              style={{ paddingLeft: `${0.5 + node.depth * 0.875}rem` }}
              className={cx(
                'flex w-full items-center justify-between gap-2 rounded-md py-1 pr-2 text-left text-sm transition-colors',
                FOCUS_RING,
                pressed ? 'bg-brand-soft text-brand' : 'text-text-muted hover:bg-surface-2 hover:text-text',
              )}
            >
              <span className="truncate">{node.display_name}</span>
              <span className="tabular-nums text-xs text-text-faint">{node.ingredient_count}</span>
            </button>
          </li>
        )
      })}
    </ul>
  )
}
