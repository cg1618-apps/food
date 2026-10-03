// Frontend: 範本 on 設定 - the recipe templates a new recipe can start from,
// in the order the new-recipe chooser offers them.
//
// Each row is the template's name, a link to its form (/edit/templates/:id),
// how many lines and steps it holds, 改名 in place and 刪除 after asking.
// 「＋ 新增範本」 opens an empty form; a recipe's page makes one from that
// recipe with 存成範本.
//
// Rows are reordered by their drag handle and the order is saved at once -
// PUT {ids}, the whole order - with media's rule as hooks/useSortOrderMove.js
// applies it: the new order is shown immediately, the list is frozen until
// the PUT has landed and the list has been read again, and a refusal puts the
// stored order back with the server's sentence.
import { arrayMove } from '@dnd-kit/sortable'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import { endpoints } from '../../api/endpoints'
import { useApiMutation, useApiQuery } from '../../hooks/useApi'
import { cx } from '../../lib/cx'
import ConfirmModal from '../modals/ConfirmModal'
import { Button, Input, LinkButton, Section } from '../ui/primitives'
import { DragHandle, SortableItem, SortableList } from '../ui/Sortable'
import { Empty, ErrorNote, Loading } from '../ui/states'

const TITLE = '範本'
const INVALIDATE = [endpoints.templates.list()]

export default function TemplatesEditor() {
  const list = useApiQuery(endpoints.templates.list())
  const reorder = useApiMutation({ method: 'PUT', invalidate: INVALIDATE })
  const [pending, setPending] = useState(null)
  const [error, setError] = useState(null)

  const stored = list.data ?? []
  const shown = pending ? pending.map((id) => stored.find((row) => row.id === id)).filter(Boolean) : stored
  const moving = pending !== null
  const ids = shown.map((row) => row.id)

  async function move(from, to) {
    if (moving) return
    const next = arrayMove(ids, from, to)
    setPending(next)
    setError(null)
    try {
      await reorder.mutateAsync({ url: endpoints.templates.order(), body: { ids: next } })
    } catch (caught) {
      setError(caught)
    } finally {
      setPending(null)
    }
  }

  return (
    <Section
      title={TITLE}
      actions={
        <LinkButton to="/edit/templates/new" size="sm">
          ＋ 新增範本
        </LinkButton>
      }
    >
      <p className="text-sm text-text-muted">
        新增食譜時可以從範本開始，帶入材料、步驟、做法和器材。拖曳排序，順序就是挑選時的順序。食譜頁的「存成範本」也會加到這裡。
      </p>

      {list.isPending ? <Loading /> : null}
      {list.isError ? <ErrorNote error={list.error} /> : null}
      {list.isSuccess && shown.length === 0 ? <Empty>還沒有範本。</Empty> : null}

      {error ? <ErrorNote error={error} /> : null}

      {shown.length ? (
        // Outside the <ul>, as on every 設定 list: dnd-kit draws its hidden
        // screen-reader text beside its children, and a <ul> holds only <li>.
        <SortableList ids={ids} onMove={move} disabled={moving}>
          <ul className="space-y-1" aria-label={TITLE}>
            {shown.map((row) => (
              <TemplateRow key={row.id} template={row} />
            ))}
          </ul>
        </SortableList>
      ) : null}
    </Section>
  )
}

// One template: rename inline (Enter saves, Escape puts the row back) and
// delete after asking, a refusal explained in the row, as NameRow does for a
// vocabulary value - which has two name slots where a template has one.
function TemplateRow({ template }) {
  const update = useApiMutation({ method: 'PATCH', invalidate: INVALIDATE })
  const remove = useApiMutation({ method: 'DELETE', invalidate: INVALIDATE })
  const [draft, setDraft] = useState(null)
  const [confirming, setConfirming] = useState(false)
  const [error, setError] = useState(null)
  const busy = update.isPending || remove.isPending
  const name = template.name

  async function saveRename(event) {
    event.preventDefault()
    setError(null)
    try {
      await update.mutateAsync({ url: endpoints.templates.update(template.id), body: { name: draft } })
      setDraft(null)
    } catch (caught) {
      setError(caught.message)
    }
  }

  async function confirmDelete() {
    setError(null)
    try {
      await remove.mutateAsync({ url: endpoints.templates.remove(template.id) })
    } catch (caught) {
      setError(caught.message)
    } finally {
      setConfirming(false)
    }
  }

  return (
    <SortableItem id={template.id} as="li" aria-label={name}>
      <div className="rounded-md border border-border bg-surface px-2 py-1.5">
        {draft !== null ? (
          <form
            onSubmit={saveRename}
            onKeyDown={(event) => {
              if (event.key === 'Escape') setDraft(null)
            }}
            className="flex flex-wrap items-center gap-2"
          >
            <Input
              aria-label={`${name} 的新名稱`}
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              className="w-48 flex-1"
              autoFocus
            />
            <div className="flex gap-1">
              <Button type="submit" kind="primary" size="sm" disabled={busy}>
                儲存
              </Button>
              <Button size="sm" onClick={() => setDraft(null)} disabled={busy}>
                取消
              </Button>
            </div>
          </form>
        ) : (
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <DragHandle label={`「${name}」`} />
            <span className="min-w-0 flex-1">
              <Link to={`/edit/templates/${template.id}`} className="font-medium text-text hover:text-brand hover:underline">
                {name}
              </Link>
              <span className="block text-xs text-text-muted sm:inline sm:pl-2">
                材料 {template.line_count} · 步驟 {template.step_count}
              </span>
            </span>
            <div className="flex shrink-0 flex-wrap gap-1">
              <Button
                kind="ghost"
                size="sm"
                onClick={() => {
                  setError(null)
                  setDraft(name)
                }}
                disabled={busy}
                aria-label={`改名「${name}」`}
              >
                改名
              </Button>
              <Button
                kind="ghost"
                size="sm"
                className="hover:text-danger"
                onClick={() => setConfirming(true)}
                disabled={busy}
                aria-label={`刪除「${name}」`}
              >
                刪除
              </Button>
            </div>
          </div>
        )}
        {error ? (
          <p role="alert" className={cx('mt-1 text-sm text-danger', draft === null ? 'pl-6' : null)}>
            {error}
          </p>
        ) : null}
      </div>

      {confirming ? (
        <ConfirmModal
          title={`刪除「${name}」？`}
          confirmLabel="刪除"
          danger
          busy={remove.isPending}
          onConfirm={confirmDelete}
          onCancel={() => setConfirming(false)}
        >
          只刪除範本；用它開始的食譜不受影響。
        </ConfirmModal>
      ) : null}
    </SortableItem>
  )
}
