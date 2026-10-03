// Frontend: the sub-row editor every list on every form is drawn with.
//
// media's CastEditor pattern, generalised: the parent owns `rows` and gets
// every change back through `onChange`; each row has a drag handle and remove
// at its edges, and an add button sits under the list. Reordering is
// components/ui/Sortable.jsx - drag the handle, or focus it and press Up /
// Down.
//
// What a row CONTAINS is the caller's: `children(row, { index, number,
// update })` draws the cells, and `update(patch)` merges into that row. The
// list operations themselves are lib/rowList.js's reducer, tested there.
//
// Inside a SortableBoard (components/forms/GroupedRowEditor.jsx) a RowEditor
// is one container of several: `container` names it, and the board - not
// this list - does the moving, across containers too. `start` is how many
// rows come before it, so rows are numbered through the whole board.
//
//   rows       the list, each row carrying a `_key` (lib/rowList.js keyed())
//   onChange   (nextRows) => void
//   newRow     () => a fresh row for the add button
//   addLabel   the add button's words
//   itemLabel  what one row is, for the controls' accessible names ("材料")
//   empty      shown when there are no rows (optional)
//   actions    extra controls beside the add button (the step paste)
//   container  inside a SortableBoard: this list's container id
//   start      the number of rows shown before this list (default 0)
import { rowsReducer } from '../../lib/rowList'
import { Button } from '../ui/primitives'
import { DragHandle, SortableItem, SortableList } from '../ui/Sortable'

export default function RowEditor({
  rows,
  onChange,
  newRow,
  addLabel = '新增一列',
  itemLabel = '這一列',
  empty,
  actions,
  container,
  start = 0,
  children,
}) {
  const dispatch = (action) => onChange(rowsReducer(rows, action))
  // dnd-kit treats a falsy id as no id, so an unkeyed row's index is a string.
  const ids = rows.map((row, index) => row._key ?? `index-${index}`)

  return (
    <div className="space-y-2">
      {rows.length === 0 && empty ? <p className="text-sm text-text-faint">{empty}</p> : null}

      <SortableList
        ids={ids}
        container={container}
        // Inside a board an empty list is a drop zone, so it keeps a height.
        className={rows.length ? 'space-y-2' : 'min-h-2'}
        onMove={(from, to) => dispatch({ type: 'move', from, to })}
      >
        {rows.map((row, index) => (
          <SortableItem
            key={ids[index]}
            id={ids[index]}
            role="group"
            aria-label={`${itemLabel} ${start + index + 1}`}
            className="flex items-start gap-2 rounded-md border border-border bg-surface p-2"
          >
            <DragHandle label={`${itemLabel} ${start + index + 1}`} className="mt-1" />

            <div className="min-w-0 flex-1">
              {children(row, {
                index,
                number: start + index + 1,
                update: (patch) => dispatch({ type: 'update', index, patch }),
              })}
            </div>

            <button
              type="button"
              aria-label={`移除${itemLabel} ${start + index + 1}`}
              title="移除"
              onClick={() => dispatch({ type: 'remove', index })}
              className="shrink-0 rounded-sm px-1.5 py-1 text-text-faint hover:bg-surface-2 hover:text-danger focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand"
            >
              ✕
            </button>
          </SortableItem>
        ))}
      </SortableList>

      <div className="flex flex-wrap items-center gap-2">
        <Button size="sm" onClick={() => dispatch({ type: 'add', row: newRow() })}>
          ＋ {addLabel}
        </Button>
        {actions}
      </div>
    </div>
  )
}
