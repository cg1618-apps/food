// Frontend: an ingredient's 保存 rows as a state x method grid.
//
// Storage is unique on (state, method), so each cell holds at most one row.
// Rows are the states (未使用 / 已開封 / 熟食) and columns the methods, both in
// the fixed vocabularies' order (GET /api/vocabularies/fixed), and a state or
// a method with nothing in it is left out: a grid of seven methods for an
// ingredient that is only ever refrigerated would be mostly dashes.
import { formatDays } from './format'

/**
 * `rows` is the ingredient's `preservation`; `states` and `methods` the fixed
 * lists (`[{ value, label }]`). Answers `{ columns, rows }` where a column is
 * `{ value, label }` and a row is `{ value, label, cells }`, `cells` holding
 * one entry per column: `{ days, notes }` or null for an empty cell. Values
 * missing from the fixed lists (an older list, a newer row) still show, after
 * the known ones.
 */
export function buildStorageGrid(rows, states = [], methods = []) {
  const entries = rows ?? []
  const present = (list, field) => {
    const used = new Set(entries.map((entry) => entry[field]))
    const known = (list ?? []).filter((item) => used.has(item.value))
    const knownValues = new Set(known.map((item) => item.value))
    const extra = [...used]
      .filter((value) => !knownValues.has(value))
      .map((value) => ({ value, label: value }))
    return [...known, ...extra]
  }

  const columns = present(methods, 'method')
  const gridRows = present(states, 'state').map((state) => ({
    ...state,
    cells: columns.map((column) => {
      const entry = entries.find((e) => e.state === state.value && e.method === column.value)
      if (!entry) return null
      return {
        days: formatDays({ min: entry.duration_min_days, max: entry.duration_max_days }),
        notes: entry.notes || null,
      }
    }),
  }))
  return { columns, rows: gridRows }
}
