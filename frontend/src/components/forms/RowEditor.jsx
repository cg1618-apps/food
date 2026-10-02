// Frontend: the sub-row editor every list on every form is drawn with.
//
// media's CastEditor pattern, generalised: the parent owns `rows` and gets
// every change back through `onChange`; each row has Move up / Move down and
// remove at its edges, and an add button sits under the list. No drag
// library, as in media - two buttons work on a phone, with a keyboard and
// with a screen reader, and a drag does not reliably do any of the three.
//
// What a row CONTAINS is the caller's: `children(row, { index, update })`
// draws the cells, and `update(patch)` merges into that row. The list
// operations themselves are lib/rowList.js's reducer, tested there.
//
//   rows       the list, each row carrying a `_key` (lib/rowList.js keyed())
//   onChange   (nextRows) => void
//   newRow     () => a fresh row for the add button
//   addLabel   the add button's words
//   itemLabel  what one row is, for the buttons' accessible names ("材料")
//   empty      shown when there are no rows (optional)
//   actions    extra controls beside the add button (the step paste)
import { Button } from '../ui/primitives'
import { rowsReducer } from '../../lib/rowList'

export default function RowEditor({
  rows,
  onChange,
  newRow,
  addLabel = '新增一列',
  itemLabel = '這一列',
  empty,
  actions,
  children,
}) {
  const dispatch = (action) => onChange(rowsReducer(rows, action))

  return (
    <div className="space-y-2">
      {rows.length === 0 && empty ? <p className="text-sm text-text-faint">{empty}</p> : null}

      {rows.map((row, index) => (
        <div
          key={row._key ?? index}
          role="group"
          aria-label={`${itemLabel} ${index + 1}`}
          className="flex items-start gap-2 rounded-md border border-border bg-surface p-2"
        >
          <div className="flex shrink-0 flex-col pt-1">
            <MoveButton
              label={`上移${itemLabel} ${index + 1}`}
              disabled={index === 0}
              onClick={() => dispatch({ type: 'move', index, delta: -1 })}
            >
              ▲
            </MoveButton>
            <MoveButton
              label={`下移${itemLabel} ${index + 1}`}
              disabled={index === rows.length - 1}
              onClick={() => dispatch({ type: 'move', index, delta: 1 })}
            >
              ▼
            </MoveButton>
          </div>

          <div className="min-w-0 flex-1">
            {children(row, {
              index,
              update: (patch) => dispatch({ type: 'update', index, patch }),
            })}
          </div>

          <button
            type="button"
            aria-label={`移除${itemLabel} ${index + 1}`}
            title="移除"
            onClick={() => dispatch({ type: 'remove', index })}
            className="shrink-0 rounded-sm px-1.5 py-1 text-text-faint hover:bg-surface-2 hover:text-danger focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand"
          >
            ✕
          </button>
        </div>
      ))}

      <div className="flex flex-wrap items-center gap-2">
        <Button size="sm" onClick={() => dispatch({ type: 'add', row: newRow() })}>
          ＋ {addLabel}
        </Button>
        {actions}
      </div>
    </div>
  )
}

function MoveButton({ label, disabled, onClick, children }) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      disabled={disabled}
      onClick={onClick}
      className="rounded-sm px-1 text-[10px] leading-4 text-text-faint hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand disabled:opacity-25"
    >
      {children}
    </button>
  )
}
