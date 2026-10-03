// Frontend: 常用食材 on 設定 - the ingredients the recipe form offers as
// one-tap chips above its 材料, in the order they are offered.
//
// The list is replaced whole (PUT {ingredient_ids}, api/endpoints.js), so
// every change - a drag, a ✕, a pick in the add box - sends the list as it
// should now be. media's rule for a change that saves at once, as
// hooks/useSortOrderMove.js applies it to the vocabularies: the new list is
// shown immediately, the list is frozen until the PUT has landed and the list
// has been read again, and a failure puts the stored list back with the
// server's sentence. The freeze is what keeps a second change from being
// built on a list the first has not finished writing.
//
// The add box picks existing ingredients only - no 「新增」: a chip for a
// name that is not in the library yet would make a stub nobody asked for, and
// one already listed is never offered.
import { arrayMove } from '@dnd-kit/sortable'
import { useState } from 'react'

import { endpoints } from '../../api/endpoints'
import { useApiMutation, useApiQuery } from '../../hooks/useApi'
import Typeahead from '../forms/Typeahead'
import { Badge, Section } from '../ui/primitives'
import { DragHandle, SortableItem, SortableList } from '../ui/Sortable'
import { Empty, ErrorNote, Loading } from '../ui/states'

const TITLE = '常用食材'

export default function CommonIngredientsEditor() {
  const list = useApiQuery(endpoints.commonIngredients.list())
  const replace = useApiMutation({ method: 'PUT', invalidate: [endpoints.commonIngredients.list()] })
  const [pending, setPending] = useState(null)
  const [error, setError] = useState(null)

  const stored = (list.data ?? []).map((row) => row.ingredient)
  const shown = pending ?? stored
  const saving = pending !== null

  async function change(next) {
    if (saving) return
    setPending(next)
    setError(null)
    try {
      await replace.mutateAsync({
        url: endpoints.commonIngredients.replace(),
        body: { ingredient_ids: next.map((ingredient) => ingredient.id) },
      })
    } catch (caught) {
      setError(caught)
    } finally {
      setPending(null)
    }
  }

  const ids = shown.map((ingredient) => ingredient.id)

  return (
    <Section title={TITLE}>
      <p className="text-sm text-text-muted">
        食譜表單的「材料」上方會列出這些食材，點一下就加一行。拖曳排序，順序就是表單上的順序。
      </p>

      {list.isPending ? <Loading /> : null}
      {list.isError ? <ErrorNote error={list.error} /> : null}
      {list.isSuccess && shown.length === 0 ? <Empty>還沒有常用食材。從下面搜尋加入。</Empty> : null}

      {error ? <ErrorNote error={error} /> : null}

      {shown.length ? (
        // Outside the <ul>, as on every 設定 list: dnd-kit draws its hidden
        // screen-reader text beside its children, and a <ul> holds only <li>.
        <SortableList
          ids={ids}
          onMove={(from, to) => change(arrayMove(shown, from, to))}
          disabled={saving}
        >
          <ul className="space-y-1" aria-label={TITLE}>
            {shown.map((ingredient) => {
              const name = ingredient.display_name
              return (
                <SortableItem key={ingredient.id} id={ingredient.id} as="li" aria-label={name}>
                  <div className="flex items-center gap-2 rounded-md border border-border bg-surface px-2 py-1.5">
                    <DragHandle label={`「${name}」`} />
                    <span className="min-w-0 flex-1 truncate font-medium text-text">{name}</span>
                    {ingredient.needs_detail ? <Badge kind="stub" /> : null}
                    <button
                      type="button"
                      onClick={() => change(shown.filter((row) => row.id !== ingredient.id))}
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
            })}
          </ul>
        </SortableList>
      ) : null}

      {list.isSuccess ? (
        <Typeahead
          sources={['ingredient']}
          label="加常用食材"
          placeholder="搜尋食材加入…"
          exclude={{ ingredient: ids }}
          // Off while a change saves: change() ignores a pick made then.
          disabled={saving}
          onSelect={(option) =>
            change([
              ...shown,
              { id: option.id, display_name: option.label, needs_detail: option.needsDetail },
            ])
          }
          className="sm:max-w-sm"
        />
      ) : null}
    </Section>
  )
}
