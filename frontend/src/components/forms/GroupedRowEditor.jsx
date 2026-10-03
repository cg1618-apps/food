// Frontend: rows that sit in groups - a recipe's 材料 and 步驟.
//
// The rows with no group come first, then each group as a box of its own:
// a header with its drag handle, its name and 移除分組, its rows, and its own
// add button, so a row added there belongs to it. 「＋ 加分組」 under the
// boxes offers the 設定 values this list does not use yet as one-tap chips,
// and a box to type a one-off name; a typed name that is a 設定 value (any
// case) is that value. The header's name box renames or repicks the same way.
// Removing a group moves its rows to the end of the ungrouped rows - nothing
// is lost, and the hint under the add control says so.
//
// The whole thing is one components/ui/Sortable.jsx SortableBoard: rows drag
// within a group and between groups, groups drag by their header handle,
// and the keyboard path crosses a group's edge (Up on a group's first row
// puts it at the end of the group above). Every row is a RowEditor container;
// the state and its operations are lib/groupedRows.js.
//
//   value      { ungrouped, groups } (lib/groupedRows.js)
//   onChange   (nextValue) => void
//   values     the 設定 list the groups are picked from ([{ id, display_name, … }])
//   newRow     () => a fresh row
//   itemLabel  one row ("材料"), numbered through the whole list
//   addLabel   the add button's words ("加一行材料")
//   groupLabel what a group is ("材料分組")
//   actions    extra controls beside the ungrouped add button
//   children   (row, { index, number, update }) => the row's cells
import { useId, useState } from 'react'

import {
  UNGROUPED,
  containerIds,
  groupedReducer,
  newGroup,
  rowsOf,
  setRows,
  startOf,
  valueNamed,
} from '../../lib/groupedRows'
import { blankToNull } from '../../lib/rowList'
import { DragHandle, SortableBoard, SortableContainers, SortableItem } from '../ui/Sortable'
import { Button, Input } from '../ui/primitives'
import RowEditor from './RowEditor'

const groupTitle = (group, index) => blankToNull(group.name) ?? `第 ${index + 1} 組`

export default function GroupedRowEditor({
  value,
  onChange,
  values,
  newRow,
  itemLabel,
  addLabel,
  groupLabel,
  actions,
  children,
}) {
  const dispatch = (action) => onChange(groupedReducer(value, action))
  const containers = containerIds(value).map((id) => ({
    id,
    items: rowsOf(value, id).map((row) => row._key),
  }))
  const listId = useId()

  const rowEditor = (container, extra = {}) => (
    <RowEditor
      container={container}
      rows={rowsOf(value, container)}
      start={startOf(value, container)}
      onChange={(rows) => onChange(setRows(value, container, rows))}
      newRow={newRow}
      itemLabel={itemLabel}
      addLabel={addLabel}
      {...extra}
    >
      {children}
    </RowEditor>
  )

  // A name typed into a header: a 設定 value it names, else a one-off.
  const rename = (key, name) =>
    dispatch({ type: 'updateGroup', key, patch: { name, groupId: valueNamed(values, name)?.id ?? null } })

  return (
    <SortableBoard
      containers={containers}
      onMoveItem={(from, to) => dispatch({ type: 'moveRow', from, to })}
      onMoveContainer={(from, to) => dispatch({ type: 'moveGroup', from, to })}
    >
      <div className="space-y-3">
        {rowEditor(UNGROUPED, { actions })}

        <datalist id={listId}>
          {(values ?? []).map((option) => (
            <option key={option.id} value={option.display_name} />
          ))}
        </datalist>

        <SortableContainers ids={value.groups.map((group) => group._key)}>
          {value.groups.map((group, index) => {
            const title = groupTitle(group, index)
            return (
              <SortableItem
                key={group._key}
                id={group._key}
                as="section"
                aria-label={`${groupLabel}「${title}」`}
                className="space-y-2 rounded-lg border-2 border-border bg-surface-2 p-2 sm:p-3"
              >
                <div className="flex items-center gap-2">
                  <DragHandle label={`${groupLabel}「${title}」`} />
                  <Input
                    aria-label={`${groupLabel} ${index + 1} 名稱`}
                    placeholder="分組名稱"
                    list={listId}
                    value={group.name}
                    onChange={(event) => rename(group._key, event.target.value)}
                    className="min-w-0 flex-1 font-bold"
                  />
                  <span className="hidden shrink-0 text-xs text-text-faint sm:inline">
                    {group.groupId ? '設定裡的分組' : '只用在這道'}
                  </span>
                  <Button
                    size="sm"
                    aria-label={`移除${groupLabel}「${title}」`}
                    title="移除分組；裡面的項目會移到最上面的不分組區，不會刪掉"
                    onClick={() => dispatch({ type: 'removeGroup', key: group._key })}
                  >
                    移除分組
                  </Button>
                </div>
                {rowEditor(group._key, { addLabel: `${addLabel}到「${title}」` })}
              </SortableItem>
            )
          })}
        </SortableContainers>

        <AddGroup value={value} values={values} groupLabel={groupLabel} onAdd={(group) => dispatch({ type: 'addGroup', group })} />
      </div>
    </SortableBoard>
  )
}

// 「＋ 加分組」: the unused 設定 values as chips, or a typed one-off name.
function AddGroup({ value, values, groupLabel, onAdd }) {
  const [open, setOpen] = useState(false)
  const [typed, setTyped] = useState('')
  const used = new Set(value.groups.map((group) => group.groupId).filter(Boolean))
  const unused = (values ?? []).filter((option) => !used.has(option.id))
  const name = blankToNull(typed)
  const named = name ? valueNamed(values, name) : null
  const taken =
    name &&
    value.groups.some((group) =>
      named ? group.groupId === named.id : blankToNull(group.name)?.toLowerCase() === name.toLowerCase(),
    )

  const add = (group) => {
    onAdd(newGroup(group))
    setTyped('')
    setOpen(false)
  }

  if (!open) {
    return (
      <div className="space-y-1">
        <Button size="sm" onClick={() => setOpen(true)}>
          ＋ 加分組
        </Button>
        {value.groups.length ? (
          <p className="text-xs text-text-faint">移除分組時，裡面的項目會移到最上面的不分組區，不會刪掉。</p>
        ) : null}
      </div>
    )
  }

  return (
    <div role="group" aria-label={`加${groupLabel}`} className="space-y-2 rounded-md border border-dashed border-border p-2">
      {unused.length ? (
        <div className="flex flex-wrap gap-1.5">
          {unused.map((option) => (
            <button
              key={option.id}
              type="button"
              onClick={() => add({ groupId: option.id, name: option.display_name })}
              className="rounded-full border border-border bg-surface px-2.5 py-0.5 text-sm text-text-muted hover:border-border-strong hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand"
            >
              ＋ {option.display_name}
            </button>
          ))}
        </div>
      ) : (
        <p className="text-xs text-text-faint">設定裡的{groupLabel}都用上了；可以打一個只用在這道的名稱。</p>
      )}
      <div className="flex flex-wrap items-center gap-2">
        <Input
          aria-label="自訂分組名稱"
          placeholder="或打一個只用在這道的名稱"
          value={typed}
          onChange={(event) => setTyped(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter') {
              event.preventDefault()
              if (name && !taken) add(named ? { groupId: named.id, name: named.display_name } : { name })
            }
          }}
          className="min-w-0 flex-1 sm:max-w-xs"
        />
        <Button
          size="sm"
          disabled={!name || taken}
          onClick={() => add(named ? { groupId: named.id, name: named.display_name } : { name })}
        >
          加入
        </Button>
        <Button size="sm" kind="ghost" onClick={() => setOpen(false)}>
          取消
        </Button>
      </div>
      {taken ? <p className="text-xs text-danger">這道已經有「{name}」這個分組了。</p> : null}
    </div>
  )
}
