// Frontend: a list of rows that sit in groups - a recipe's 材料 and 步驟 in the
// form.
//
// The shape is the one the page shows: rows with no group first, then each
// group with its own rows.
//
//   { ungrouped: [row], groups: [{ _key, groupId, name, rows: [row] }] }
//
// A group names a 設定 value (`groupId`, with `name` its display name, kept
// for showing) or carries a one-off `name` (`groupId` null). Rows carry a
// `_key` as every form row does (lib/rowList.js), and so do groups: the two
// share one drag area (components/ui/Sortable.jsx's SortableBoard), so their
// keys must not collide, and nextKey() never repeats.
//
// A place in the list is `{ container, index }`, `container` being UNGROUPED
// or a group's `_key`. The operations are one pure reducer, tested in
// groupedRows.test.js, so the form only dispatches.

import { arrayMove } from '@dnd-kit/sortable'

import { blankToNull, keyed, nextKey, rowsReducer } from './rowList'

/** The container id of the rows with no group. */
export const UNGROUPED = 'ungrouped'

export const emptyGrouped = () => ({ ungrouped: [], groups: [] })

/** A new group: a 設定 value `{ id, display_name }`, or a one-off name. */
export function newGroup({ groupId = null, name = '', rows = [] } = {}) {
  return { _key: nextKey(), groupId, name, rows: rows.map(keyed) }
}

/** The container ids in display order: UNGROUPED, then each group's key. */
export function containerIds(state) {
  return [UNGROUPED, ...state.groups.map((group) => group._key)]
}

/** The rows of one container. */
export function rowsOf(state, container) {
  if (container === UNGROUPED) return state.ungrouped
  return state.groups.find((group) => group._key === container)?.rows ?? []
}

/** The state with one container's rows replaced - what a RowEditor's
 * onChange hands back. */
export function setRows(state, container, rows) {
  if (container === UNGROUPED) return { ...state, ungrouped: rows }
  return {
    ...state,
    groups: state.groups.map((group) => (group._key === container ? { ...group, rows } : group)),
  }
}

/** One row, found by its `_key` in whichever container holds it, patched. */
export function updateRowByKey(state, key, patch) {
  const patchRows = (rows) => rows.map((row) => (row._key === key ? { ...row, ...patch } : row))
  return {
    ungrouped: patchRows(state.ungrouped),
    groups: state.groups.map((group) => ({ ...group, rows: patchRows(group.rows) })),
  }
}

/** Every row in display order - what continuous numbering counts through. */
export function flatRows(state) {
  return [...state.ungrouped, ...state.groups.flatMap((group) => group.rows)]
}

/** The number the first row of `container` is shown with, less one. */
export function startOf(state, container) {
  if (container === UNGROUPED) return 0
  let start = state.ungrouped.length
  for (const group of state.groups) {
    if (group._key === container) return start
    start += group.rows.length
  }
  return start
}

/** Whether a group name is the same one, as the server compares them. */
const sameName = (a, b) => String(a ?? '').trim().toLowerCase() === String(b ?? '').trim().toLowerCase()

/**
 * A typed group name against the 設定 values `[{ id, display_name, name_cn,
 * name_en }]`: the value it names (trimmed, any case), or null for a one-off.
 */
export function valueNamed(values, name) {
  return (
    (values ?? []).find((value) =>
      [value.display_name, value.name_cn, value.name_en].some((slot) => slot && sameName(slot, name)),
    ) ?? null
  )
}

/**
 * Apply one action and return the new state. Never mutates.
 *
 *   { type: 'rows', container, action }  a lib/rowList.js action (add,
 *                                        insert, update, remove, move) on
 *                                        one container's rows - the step
 *                                        paste's 'insert', say
 *   { type: 'moveRow', from, to }        `{ container, index }` to another
 *                                        place, in the same container or not;
 *                                        `to.index` is where it ends up
 *   { type: 'addGroup', group }          append (newGroup())
 *   { type: 'updateGroup', key, patch }  rename or repick
 *   { type: 'removeGroup', key }         the group goes; its rows move to
 *                                        the end of the ungrouped rows
 *   { type: 'moveGroup', from, to }      reorder the groups by index
 */
export function groupedReducer(state, action) {
  switch (action.type) {
    case 'rows':
      return setRows(state, action.container, rowsReducer(rowsOf(state, action.container), action.action))
    case 'moveRow': {
      const { from, to } = action
      if (from.container === to.container) {
        const rows = rowsOf(state, from.container)
        return setRows(state, from.container, rowsReducer(rows, { type: 'move', from: from.index, to: to.index }))
      }
      const source = rowsOf(state, from.container)
      const row = source[from.index]
      if (!row || !containerIds(state).includes(to.container)) return state
      const target = [...rowsOf(state, to.container)]
      target.splice(Math.max(0, Math.min(to.index, target.length)), 0, row)
      const removed = setRows(state, from.container, source.filter((_, i) => i !== from.index))
      return setRows(removed, to.container, target)
    }
    case 'addGroup':
      return { ...state, groups: [...state.groups, action.group._key ? action.group : newGroup(action.group)] }
    case 'updateGroup':
      return {
        ...state,
        groups: state.groups.map((group) => (group._key === action.key ? { ...group, ...action.patch } : group)),
      }
    case 'removeGroup': {
      const group = state.groups.find((g) => g._key === action.key)
      if (!group) return state
      return {
        ungrouped: [...state.ungrouped, ...group.rows],
        groups: state.groups.filter((g) => g._key !== action.key),
      }
    }
    case 'moveGroup': {
      const { from, to } = action
      const count = state.groups.length
      if (from === to || from < 0 || to < 0 || from >= count || to >= count) return state
      return { ...state, groups: arrayMove(state.groups, from, to) }
    }
    default:
      throw new Error(`Unknown grouped action: ${action.type}`)
  }
}

/**
 * The form's groups -> the `line_groups` / `step_groups` payload, each group
 * carrying its rows through `rowsPayload(rows, start)`. `idField` is
 * 'line_group_id' or 'step_group_id'. A group with no name is refused with a
 * sentence naming it by its place, rather than sent to fail.
 */
export function groupsPayload(state, { idField, inner, rowsPayload, what }) {
  return state.groups.map((group, index) => {
    const rows = rowsPayload(group.rows, startOf(state, group._key))
    if (group.groupId) return { [idField]: group.groupId, [inner]: rows }
    const name = blankToNull(group.name)
    if (!name) throw new Error(`第 ${index + 1} 個${what}還沒有名稱：打一個名稱，或移除這個分組。`)
    return { name, [inner]: rows }
  })
}

/** A recipe response's groups -> the form's groups, rows through `toRow`. */
export function groupsFromResponse(groups, inner, toRow) {
  return (groups ?? []).map((group) =>
    newGroup({
      groupId: group.group?.id ?? null,
      name: group.display_name ?? group.name ?? '',
      rows: (group[inner] ?? []).map(toRow),
    }),
  )
}
