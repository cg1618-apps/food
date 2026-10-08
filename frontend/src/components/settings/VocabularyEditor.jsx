// Frontend: one flat vocabulary on 設定 - courses, regions, recipe statuses,
// source platforms, authors, 材料分組 / 步驟分組, cooking methods, equipment.
// Add, rename, reorder and delete, each in place. Labels are not one of
// these: they are grouped by library, in LabelEditor.jsx.
//
// The factory vocabularies (app/routers/vocabulary.py) carry a sort_order and
// are reordered by dragging (lib/vocabulary.js decides the PATCHes,
// hooks/useSortOrderMove.js holds the list still while they land); authors
// are listed by name, so `ordered` is off for them. A new value goes after
// the last one.
//
//   title       the section heading
//   endpoints   the resource's group in api/endpoints.js
//   invalidate  every read prefix a change here makes stale - the
//               vocabulary's own list and the owners that show its names
//   ordered     whether the list has a sort_order to move by
//   hint        one line under the heading saying what the vocabulary is for
//   addLabel    the add button's words
//   meta        (row) => the count line
//   confirmText (row) => what the delete question says
//   refusal     (row, error) => the inline sentence when a delete fails
import { useApiMutation, useApiQuery } from '../../hooks/useApi'
import { useSortOrderMove } from '../../hooks/useSortOrderMove'
import { nextSortOrder } from '../../lib/vocabulary'
import { Section } from '../ui/primitives'
import { SortableList } from '../ui/Sortable'
import { Empty, ErrorNote, Loading } from '../ui/states'
import AddNameForm from './AddNameForm'
import NameRow from './NameRow'

export default function VocabularyEditor({
  title,
  endpoints: group,
  invalidate,
  ordered = true,
  hint,
  addLabel,
  meta,
  confirmText,
  refusal,
}) {
  const list = useApiQuery(group.list())
  const create = useApiMutation({ method: 'POST', invalidate })
  const update = useApiMutation({ method: 'PATCH', invalidate })
  const remove = useApiMutation({ method: 'DELETE', invalidate })

  const sorter = useSortOrderMove((id, sort_order) =>
    update.mutateAsync({ url: group.update(id), body: { sort_order } }),
  )
  const rows = sorter.ordered(list.data ?? [])

  const items = rows.map((row) => (
    <NameRow
      key={row.id}
      item={row}
      meta={meta(row)}
      onRename={(names) => update.mutateAsync({ url: group.update(row.id), body: names })}
      sortable={ordered}
      onDelete={() => remove.mutateAsync({ url: group.remove(row.id) })}
      confirmText={confirmText(row)}
      refusal={(error) => refusal(row, error)}
    />
  ))

  return (
    <Section title={title}>
      {hint ? <p className="text-sm text-text-muted">{hint}</p> : null}

      {list.isPending ? <Loading /> : null}
      {list.isError ? <ErrorNote error={list.error} /> : null}
      {list.isSuccess && rows.length === 0 ? <Empty>還沒有任何{title}。</Empty> : null}

      {sorter.error ? <ErrorNote error={sorter.error} /> : null}

      {rows.length && ordered ? (
        // The SortableList goes outside the list: dnd-kit draws its hidden
        // screen-reader text beside its children, and a <ul> holds only <li>.
        <SortableList
          ids={rows.map((row) => row.id)}
          onMove={(from, to) => sorter.move(rows, from, to)}
          disabled={sorter.moving}
        >
          <ul className="space-y-1" aria-label={title}>
            {items}
          </ul>
        </SortableList>
      ) : null}
      {rows.length && !ordered ? (
        <ul className="space-y-1" aria-label={title}>
          {items}
        </ul>
      ) : null}

      {list.isSuccess ? (
        <AddNameForm
          label={addLabel}
          onAdd={(names) =>
            create.mutateAsync({
              url: group.create(),
              body: ordered ? { ...names, sort_order: nextSortOrder(rows) } : names,
            })
          }
        />
      ) : null}
    </Section>
  )
}
