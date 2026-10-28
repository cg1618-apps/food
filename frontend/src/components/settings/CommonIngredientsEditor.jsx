// Frontend: 常用食材 on 未來固定設定 - the ingredients the recipe form offers as
// one-tap chips above its 材料, 未分組 first and then in the owner's named
// groups (肉, 調味料 …), in the order they are offered.
//
// The structure is replaced whole (PUT {ungrouped, groups},
// api/endpoints.js), so every change - a drag, a ✕, a pick in the add box, a
// group added, renamed, dragged or deleted - sends the structure as it should
// now be. media's rule for a change that saves at once, as
// hooks/useSortOrderMove.js applies it to the vocabularies: the new structure
// is shown immediately, everything is frozen until the PUT has landed and the
// structure has been read again, and a failure puts the stored one back with
// the server's sentence. The freeze is what keeps a second change from being
// built on a structure the first has not finished writing.
//
// The groups are the recipe form's pattern (GroupedRowEditor): one
// components/ui/Sortable.jsx SortableBoard, chips dragged within a group and
// between groups, groups dragged by their header, the keyboard path crossing
// a group's edge; the operations are lib/groupedRows.js's reducer. With no
// group at all the list is drawn as it always was, with no 未分組 heading.
//
// A group's name is edited in its header and saved when the box is left or
// Enter is pressed; Escape, a blank name or one another group has (any case)
// puts the stored name back. Deleting a group asks first, as every delete on
// 設定 does, and moves its chips to the end of 未分組 - nothing is lost.
//
// The add box picks existing ingredients only - no 「新增」: a chip for a
// name that is not in the library yet would make a stub nobody asked for, and
// one already listed, in any group, is never offered. A pick goes to the end
// of 未分組, to be dragged where it belongs.
import { useState } from 'react'

import { endpoints } from '../../api/endpoints'
import { useApiMutation, useApiQuery } from '../../hooks/useApi'
import { UNGROUPED, flatRows, groupedReducer, newGroup } from '../../lib/groupedRows'
import { blankToNull } from '../../lib/rowList'
import Typeahead from '../forms/Typeahead'
import ConfirmModal from '../modals/ConfirmModal'
import { Badge, Button, Input, Section } from '../ui/primitives'
import { DragHandle, SortableBoard, SortableContainers, SortableItem, SortableList } from '../ui/Sortable'
import { Empty, ErrorNote, Loading } from '../ui/states'

const TITLE = '常用食材'
const UNGROUPED_TITLE = '未分組'

// Keys from the stored ids, so a re-read after a save keeps every row and
// group where React already has it. A group made in this change has none
// yet and takes newGroup()'s.
const chip = (ingredient) => ({ ...ingredient, _key: `ingredient-${ingredient.id}` })

function fromResponse(data) {
  return {
    ungrouped: (data?.ungrouped ?? []).map(chip),
    groups: (data?.groups ?? []).map((group) => ({
      _key: `group-${group.id}`,
      groupId: group.id,
      name: group.name,
      rows: group.ingredients.map(chip),
    })),
  }
}

function toPayload(state) {
  return {
    ungrouped: state.ungrouped.map((row) => row.id),
    groups: state.groups.map((group) => ({
      ...(group.groupId ? { id: group.groupId } : {}),
      name: group.name,
      ingredient_ids: group.rows.map((row) => row.id),
    })),
  }
}

const sameName = (a, b) => a.trim().toLowerCase() === b.trim().toLowerCase()
const nameTaken = (state, name, exceptKey = null) =>
  state.groups.some((group) => group._key !== exceptKey && sameName(group.name, name))

export default function CommonIngredientsEditor() {
  const query = useApiQuery(endpoints.commonIngredients.list())
  const replace = useApiMutation({ method: 'PUT', invalidate: [endpoints.commonIngredients.list()] })
  const [pending, setPending] = useState(null)
  const [error, setError] = useState(null)
  const [deleting, setDeleting] = useState(null)

  const shown = pending ?? fromResponse(query.data)
  const saving = pending !== null
  const listedIds = flatRows(shown).map((row) => row.id)
  const hasGroups = shown.groups.length > 0

  async function change(next) {
    if (saving) return
    setPending(next)
    setError(null)
    try {
      await replace.mutateAsync({ url: endpoints.commonIngredients.replace(), body: toPayload(next) })
    } catch (caught) {
      setError(caught)
    } finally {
      setPending(null)
    }
  }

  const dispatch = (action) => change(groupedReducer(shown, action))
  const removeChip = (id) =>
    change({
      ungrouped: shown.ungrouped.filter((row) => row.id !== id),
      groups: shown.groups.map((group) => ({ ...group, rows: group.rows.filter((row) => row.id !== id) })),
    })

  const containers = [
    { id: UNGROUPED, items: shown.ungrouped.map((row) => row._key) },
    ...shown.groups.map((group) => ({ id: group._key, items: group.rows.map((row) => row._key) })),
  ]

  const chips = (container, rows, label) => (
    <SortableList container={container} ids={rows.map((row) => row._key)}>
      {rows.length ? (
        <ul className="space-y-1" aria-label={label}>
          {rows.map((ingredient) => (
            <ChipRow key={ingredient._key} ingredient={ingredient} saving={saving} onRemove={removeChip} />
          ))}
        </ul>
      ) : hasGroups ? (
        <p className="rounded-md border border-dashed border-border px-2 py-1.5 text-sm text-text-faint">
          把食材拖到這裡。
        </p>
      ) : null}
    </SortableList>
  )

  return (
    <Section title={TITLE}>
      <p className="text-sm text-text-muted">
        食譜表單的「材料」上方會列出這些食材，點一下就加一行。拖曳排序，順序就是表單上的順序；可以分組，拖到別的分組就移過去。
      </p>

      {query.isPending ? <Loading /> : null}
      {query.isError ? <ErrorNote error={query.error} /> : null}
      {query.isSuccess && listedIds.length === 0 && !hasGroups ? (
        <Empty>還沒有常用食材。從下面搜尋加入。</Empty>
      ) : null}

      {error ? <ErrorNote error={error} /> : null}

      {query.isSuccess ? (
        // The lists sit outside any <ul> of their own, as on every 設定 list:
        // dnd-kit draws its hidden screen-reader text beside its children,
        // and a <ul> holds only <li>.
        <SortableBoard
          containers={containers}
          disabled={saving}
          onMoveItem={(from, to) => dispatch({ type: 'moveRow', from, to })}
          onMoveContainer={(from, to) => dispatch({ type: 'moveGroup', from, to })}
        >
          <div className="space-y-3">
            {hasGroups ? (
              <div className="space-y-2">
                <h3 className="text-sm font-bold text-text-muted">{UNGROUPED_TITLE}</h3>
                {chips(UNGROUPED, shown.ungrouped, UNGROUPED_TITLE)}
              </div>
            ) : (
              chips(UNGROUPED, shown.ungrouped, TITLE)
            )}

            <SortableContainers ids={shown.groups.map((group) => group._key)}>
              {shown.groups.map((group) => (
                <SortableItem
                  key={group._key}
                  id={group._key}
                  as="section"
                  aria-label={`分組「${group.name}」`}
                  className="space-y-2 rounded-lg border-2 border-border bg-surface-2 p-2 sm:p-3"
                >
                  <GroupHeader
                    group={group}
                    saving={saving}
                    isTaken={(name) => nameTaken(shown, name, group._key)}
                    onRename={(name) => dispatch({ type: 'updateGroup', key: group._key, patch: { name } })}
                    onDelete={() => setDeleting(group)}
                  />
                  {chips(group._key, group.rows, `「${group.name}」的食材`)}
                </SortableItem>
              ))}
            </SortableContainers>
          </div>
        </SortableBoard>
      ) : null}

      {query.isSuccess ? (
        <div className="flex flex-wrap items-start gap-3">
          <Typeahead
            sources={['ingredient']}
            label="加常用食材"
            placeholder="搜尋食材加入…"
            exclude={{ ingredient: listedIds }}
            // Off while a change saves: change() ignores a pick made then.
            disabled={saving}
            onSelect={(option) =>
              dispatch({
                type: 'rows',
                container: UNGROUPED,
                action: {
                  type: 'add',
                  row: chip({ id: option.id, display_name: option.label, needs_detail: option.needsDetail }),
                },
              })
            }
            className="min-w-0 flex-1 sm:max-w-sm"
          />
          <AddGroup
            saving={saving}
            isTaken={(name) => nameTaken(shown, name)}
            onAdd={(name) => dispatch({ type: 'addGroup', group: newGroup({ name }) })}
          />
        </div>
      ) : null}

      {deleting ? (
        <ConfirmModal
          title={`刪除分組「${deleting.name}」？`}
          confirmLabel="刪除"
          danger
          onConfirm={() => {
            setDeleting(null)
            dispatch({ type: 'removeGroup', key: deleting._key })
          }}
          onCancel={() => setDeleting(null)}
        >
          {deleting.rows.length
            ? `裡面的 ${deleting.rows.length} 個食材會移到「未分組」的最後，不會刪掉。`
            : '這個分組是空的。'}
        </ConfirmModal>
      ) : null}
    </Section>
  )
}

function ChipRow({ ingredient, saving, onRemove }) {
  const name = ingredient.display_name
  return (
    <SortableItem id={ingredient._key} as="li" aria-label={name}>
      <div className="flex items-center gap-2 rounded-md border border-border bg-surface px-2 py-1.5">
        <DragHandle label={`「${name}」`} />
        <span className="min-w-0 flex-1 truncate font-medium text-text">{name}</span>
        {ingredient.needs_detail ? <Badge kind="stub" /> : null}
        <button
          type="button"
          onClick={() => onRemove(ingredient.id)}
          disabled={saving}
          aria-label={`從常用食材移除「${name}」`}
          title="移除"
          className="shrink-0 rounded-sm px-1.5 text-text-faint hover:text-danger focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand disabled:opacity-30"
        >
          <span aria-hidden="true">✕</span>
        </button>
      </div>
    </SortableItem>
  )
}

// A group's header: its drag handle, its name - renamed in place - and 刪除.
function GroupHeader({ group, saving, isTaken, onRename, onDelete }) {
  const [draft, setDraft] = useState(null)
  const typed = draft ?? group.name
  const name = blankToNull(typed)
  const taken = name !== null && draft !== null && isTaken(name)

  const commit = () => {
    if (draft === null) return
    setDraft(null)
    if (name && !taken && name !== group.name) onRename(name)
  }

  return (
    <div className="space-y-1">
      <div className="flex items-center gap-2">
        <DragHandle label={`分組「${group.name}」`} />
        <Input
          aria-label={`分組「${group.name}」名稱`}
          placeholder="分組名稱"
          value={typed}
          disabled={saving}
          onChange={(event) => setDraft(event.target.value)}
          onBlur={commit}
          onKeyDown={(event) => {
            if (event.key === 'Enter') {
              event.preventDefault()
              commit()
            } else if (event.key === 'Escape') {
              setDraft(null)
            }
          }}
          className="min-w-0 flex-1 font-bold"
        />
        <Button
          size="sm"
          disabled={saving}
          aria-label={`刪除分組「${group.name}」`}
          title="刪除分組；裡面的食材會移到未分組，不會刪掉"
          onClick={onDelete}
        >
          刪除分組
        </Button>
      </div>
      {draft !== null && !name ? <p className="text-xs text-danger">分組要有名稱；離開時會改回「{group.name}」。</p> : null}
      {taken ? <p className="text-xs text-danger">已經有「{name}」這個分組了。</p> : null}
    </div>
  )
}

// 「＋ 新增分組」: a name, then 加入. A name another group has is refused here,
// as the server would.
function AddGroup({ saving, isTaken, onAdd }) {
  const [open, setOpen] = useState(false)
  const [typed, setTyped] = useState('')
  const name = blankToNull(typed)
  const taken = name !== null && isTaken(name)

  const add = () => {
    if (!name || taken || saving) return
    onAdd(name)
    setTyped('')
    setOpen(false)
  }

  if (!open) {
    return (
      <Button size="sm" onClick={() => setOpen(true)} disabled={saving}>
        ＋ 新增分組
      </Button>
    )
  }

  return (
    <div role="group" aria-label="新增分組" className="w-full space-y-1 rounded-md border border-dashed border-border p-2 sm:w-auto">
      <div className="flex flex-wrap items-center gap-2">
        <Input
          aria-label="新分組名稱"
          placeholder="例如 肉、調味料"
          value={typed}
          autoFocus
          onChange={(event) => setTyped(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter') {
              event.preventDefault()
              add()
            } else if (event.key === 'Escape') {
              setOpen(false)
            }
          }}
          className="min-w-0 flex-1 sm:max-w-xs"
        />
        <Button size="sm" disabled={!name || taken || saving} onClick={add}>
          加入
        </Button>
        <Button size="sm" kind="ghost" onClick={() => setOpen(false)}>
          取消
        </Button>
      </div>
      {taken ? <p className="text-xs text-danger">已經有「{name}」這個分組了。</p> : null}
    </div>
  )
}
