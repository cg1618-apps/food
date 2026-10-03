// Frontend: the ingredient category tree on 設定.
//
// The tree is drawn as nested lists, each node a NameRow: rename (and, while
// renaming, move under another parent), drag among its siblings - each
// sibling group is its own SortableList, and a node carries its children with
// it - 新增子分類 to add a child right under it, and delete. Every ingredient is
// filed in exactly one category, so a category with ingredients or children
// cannot go: both foreign keys are RESTRICT, the server answers 409, and the
// row says why with the counts the tree already carries (lib/vocabulary.js
// categoryBlockers). The fallback category - where new stubs land - offers no
// delete at all; the server refuses it anyway, and a button that always fails
// is worse than none.
import { useState } from 'react'

import { endpoints } from '../../api/endpoints'
import { useApiMutation, useApiQuery } from '../../hooks/useApi'
import { flatten, subtreeIds } from '../../lib/tree'
import { useSortOrderMove } from '../../hooks/useSortOrderMove'
import { categoryBlockers, nextSortOrder } from '../../lib/vocabulary'
import { Chip, Section, Select } from '../ui/primitives'
import { SortableList } from '../ui/Sortable'
import { Empty, ErrorNote, Loading } from '../ui/states'
import AddNameForm from './AddNameForm'
import NameRow from './NameRow'

const INVALIDATE = [endpoints.categories.tree(), endpoints.ingredients.list()]

export default function CategoryEditor() {
  const tree = useApiQuery(endpoints.categories.tree())
  const create = useApiMutation({ method: 'POST', invalidate: INVALIDATE })
  const update = useApiMutation({ method: 'PATCH', invalidate: INVALIDATE })
  const remove = useApiMutation({ method: 'DELETE', invalidate: INVALIDATE })
  const [addingUnder, setAddingUnder] = useState(null)
  const sorter = useSortOrderMove((id, sort_order) =>
    update.mutateAsync({ url: endpoints.categories.update(id), body: { sort_order } }),
  )

  const roots = tree.data ?? []
  const flat = flatten(roots)

  const childrenOf = (parentId) =>
    parentId == null ? roots : (flat.find((node) => node.id === parentId)?.children ?? [])

  async function add(parentId, names) {
    await create.mutateAsync({
      url: endpoints.categories.create(),
      body: { ...names, parent_id: parentId, sort_order: nextSortOrder(childrenOf(parentId)) },
    })
    setAddingUnder(null)
  }

  async function rename(node, draft) {
    const parentId = draft.parent_id === '' ? null : Number(draft.parent_id)
    const body = { name_cn: draft.name_cn, name_en: draft.name_en }
    if (parentId !== node.parent_id) {
      // A node moving under a new parent goes after its new siblings.
      body.parent_id = parentId
      body.sort_order = nextSortOrder(childrenOf(parentId))
    }
    await update.mutateAsync({ url: endpoints.categories.update(node.id), body })
  }

  function parentPicker(node) {
    const excluded = new Set(subtreeIds(node))
    return function ParentSelect(draft, setDraft) {
      return (
        <label className="flex items-center gap-2 text-sm text-text-muted">
          上層
          <Select
            className="w-auto"
            value={draft.parent_id}
            onChange={(e) => setDraft({ ...draft, parent_id: e.target.value })}
          >
            <option value="">（最上層）</option>
            {flat
              .filter((other) => !excluded.has(other.id))
              .map((other) => (
                <option key={other.id} value={other.id}>
                  {'　'.repeat(other.depth)}
                  {other.display_name}
                </option>
              ))}
          </Select>
        </label>
      )
    }
  }

  // One sibling group: a list of its own, so a drag stays among siblings.
  // `before` is drawn first inside it (the add-a-child form). The
  // SortableList goes outside the <ul>: dnd-kit draws its hidden
  // screen-reader text beside its children, and a <ul> holds only <li>.
  function level(siblings, { label, className, before = null }) {
    const nodes = sorter.ordered(siblings)
    return (
      <SortableList
        ids={nodes.map((node) => node.id)}
        onMove={(from, to) => sorter.move(nodes, from, to)}
        disabled={sorter.moving}
      >
        <ul className={className} aria-label={label}>
          {before}
          {nodes.map((node) => (
            <NameRow
              key={node.id}
              item={node}
              sortable
              badge={node.is_fallback ? <Chip title="新的食材先放在這裡">預設</Chip> : null}
              meta={`${node.ingredient_count} 種食材`}
              onRename={(draft) => rename(node, draft)}
              renameExtra={parentPicker(node)}
              initialExtra={{ parent_id: node.parent_id == null ? '' : String(node.parent_id) }}
              onDelete={
                node.is_fallback
                  ? undefined
                  : () => remove.mutateAsync({ url: endpoints.categories.remove(node.id) })
              }
              confirmText={categoryBlockers(node) ?? `「${node.display_name}」是空的，刪掉不會動到任何食材。`}
              refusal={(error) =>
                error?.status === 409 ? (categoryBlockers(node) ?? error.message) : error?.message
              }
              nested={
                addingUnder === node.id || node.children?.length
                  ? level(node.children ?? [], {
                      label: `${node.display_name}的子分類`,
                      className: 'ml-5 mt-1 space-y-1',
                      before:
                        addingUnder === node.id ? (
                          <li>
                            <AddNameForm
                              label={`${node.display_name}的子分類`}
                              autoFocus
                              onAdd={(names) => add(node.id, names)}
                              onCancel={() => setAddingUnder(null)}
                            />
                          </li>
                        ) : null,
                    })
                  : null
              }
            >
              <button
                type="button"
                onClick={() => setAddingUnder(node.id)}
                aria-label={`在「${node.display_name}」下新增子分類`}
                className="rounded-md px-2.5 py-1 text-xs font-medium text-text-muted hover:bg-surface-2 hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand"
              >
                ＋子分類
              </button>
            </NameRow>
          ))}
        </ul>
      </SortableList>
    )
  }

  return (
    <Section title="食材分類">
      <p className="text-sm text-text-muted">
        每種食材都放在一個分類裡；新的食材先放在「預設」那一個，它不能刪。數字只算直接放在該分類的食材。
      </p>

      {tree.isPending ? <Loading /> : null}
      {tree.isError ? <ErrorNote error={tree.error} /> : null}
      {tree.isSuccess && roots.length === 0 ? <Empty>還沒有任何分類。</Empty> : null}

      {sorter.error ? <ErrorNote error={sorter.error} /> : null}

      {roots.length ? level(roots, { label: '食材分類', className: 'space-y-1' }) : null}

      {tree.isSuccess ? <AddNameForm label="新增分類" onAdd={(names) => add(null, names)} /> : null}
    </Section>
  )
}
