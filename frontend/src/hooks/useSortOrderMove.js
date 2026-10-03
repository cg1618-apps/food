// Frontend: a drag on 設定, saved - the PATCHes lib/vocabulary.js's
// reorderPatches decides, sent at once.
//
// media's rule for a move that saves at once: the new order is shown
// immediately, the list is frozen (`moving`, for SortableList's `disabled`)
// until every PATCH has landed and the list has been read again, and a
// failure puts the stored order back with the server's sentence in `error`.
// The freeze is what keeps a second drag from being computed from an order
// the first has not finished writing.
//
//   const sorter = useSortOrderMove((id, sort_order) => patch(...))
//   sorter.ordered(rows)          rows in the order on screen
//   sorter.move(rows, from, to)   rows as ordered(), indexes into them
import { arrayMove } from '@dnd-kit/sortable'
import { useState } from 'react'

import { reorderPatches } from '../lib/vocabulary'

export function useSortOrderMove(save) {
  const [pending, setPending] = useState(null)
  const [moving, setMoving] = useState(false)
  const [error, setError] = useState(null)

  // Only the list the drag was in is reordered: the category tree calls this
  // once per sibling group, and the other groups hold none of these ids.
  function ordered(rows) {
    if (!pending || !rows.some((row) => pending.includes(row.id))) return rows
    return [...rows].sort((a, b) => pending.indexOf(a.id) - pending.indexOf(b.id))
  }

  async function move(rows, from, to) {
    const patches = reorderPatches(rows, from, to)
    if (!patches.length || moving) return
    setPending(arrayMove(rows, from, to).map((row) => row.id))
    setMoving(true)
    setError(null)
    try {
      await Promise.all(patches.map(({ id, sort_order }) => save(id, sort_order)))
    } catch (caught) {
      setError(caught)
    } finally {
      setPending(null)
      setMoving(false)
    }
  }

  return { ordered, move, moving, error }
}
