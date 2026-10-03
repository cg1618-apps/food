// Frontend: TBD's edit page, /edit/tbd - the same list as /tbd, editable in
// place.
//
// Every entry is a card: a name, its links (components/forms/RowEditor.jsx,
// a URL and an optional label each), and its own 儲存 and 刪除. A card is
// saved on its own - PATCH sends the name and every link, which replace what
// was stored - so editing one entry never touches another. 「＋ 新增」 puts an
// unsaved card at the end; its 儲存 creates it (POST), and its 取消 drops it
// without asking, since nothing has been stored.
//
// Entries are reordered by their drag handle and the order is saved at once,
// with media's rule as hooks/useSortOrderMove.js applies it: the new order is
// shown immediately, the list is frozen until the PUT has landed and the
// list has been read again, and a refusal puts the stored order back with
// the server's sentence. Unsaved cards have no handle: they have no place in
// the stored order yet.
import { arrayMove } from '@dnd-kit/sortable'
import { useState } from 'react'

import { endpoints } from '../../api/endpoints'
import RowEditor from '../../components/forms/RowEditor'
import ConfirmModal from '../../components/modals/ConfirmModal'
import { Button, Field, Input, LinkButton } from '../../components/ui/primitives'
import { DragHandle, SortableItem, SortableList } from '../../components/ui/Sortable'
import { Empty, ErrorNote, Loading } from '../../components/ui/states'
import { useApiMutation, useApiQuery } from '../../hooks/useApi'
import { blankToNull, keyed, nextKey } from '../../lib/rowList'

const TITLE = 'TBD'
const INVALIDATE = [endpoints.tbd.list()]
const NEEDS_CONTENT = '名稱或連結至少要填一個。'

function linkRows(entry) {
  return (entry?.links ?? []).map((link) => keyed({ url: link.url, label: link.label ?? '' }))
}

/** The card as a request body: an empty link row is left out, not sent. */
function payloadOf(name, links) {
  return {
    name: blankToNull(name),
    links: links
      .filter((row) => blankToNull(row.url) || blankToNull(row.label))
      .map((row) => ({ url: String(row.url ?? '').trim(), label: blankToNull(row.label) })),
  }
}

export default function TbdForm() {
  const list = useApiQuery(endpoints.tbd.list())
  const reorder = useApiMutation({ method: 'PUT', invalidate: INVALIDATE })
  const [pending, setPending] = useState(null)
  const [orderError, setOrderError] = useState(null)
  const [fresh, setFresh] = useState([])

  const stored = list.data ?? []
  const shown = pending
    ? pending.map((id) => stored.find((entry) => entry.id === id)).filter(Boolean)
    : stored
  const moving = pending !== null
  const ids = shown.map((entry) => entry.id)

  async function move(from, to) {
    if (moving) return
    const next = arrayMove(ids, from, to)
    setPending(next)
    setOrderError(null)
    try {
      await reorder.mutateAsync({ url: endpoints.tbd.order(), body: { ids: next } })
    } catch (caught) {
      setOrderError(caught)
    } finally {
      setPending(null)
    }
  }

  const drop = (key) => setFresh((keys) => keys.filter((k) => k !== key))

  let body
  if (list.isPending) body = <Loading />
  else if (list.error) body = <ErrorNote error={list.error} />
  else
    body = (
      <>
        {shown.length === 0 && fresh.length === 0 ? <Empty>還沒有任何東西。</Empty> : null}
        {/* Outside the <ul>, as on every sortable list here: dnd-kit draws its
            hidden screen-reader text beside its children, and a <ul> holds
            only <li>. */}
        <SortableList ids={ids} onMove={move} disabled={moving}>
          <ul aria-label={TITLE} className="space-y-3">
            {shown.map((entry) => (
              <EntryCard key={entry.id} entry={entry} />
            ))}
            {fresh.map((key) => (
              <EntryCard key={key} onCreated={() => drop(key)} onDiscard={() => drop(key)} />
            ))}
          </ul>
        </SortableList>
        <Button onClick={() => setFresh((keys) => [...keys, nextKey()])}>＋ 新增</Button>
      </>
    )

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h1 className="text-3xl font-bold">編輯 {TITLE}</h1>
        <LinkButton to="/tbd" size="sm">
          完成
        </LinkButton>
      </div>
      {orderError ? <ErrorNote error={orderError} /> : null}
      {body}
    </div>
  )
}

// One entry. `entry` is the stored row; without one the card is new and
// unsaved. The card keeps what is typed in its own state, so a refetch after
// another card's save never throws it away.
function EntryCard({ entry, onCreated, onDiscard }) {
  const isNew = !entry
  const label = isNew ? '新項目' : (entry.name ?? '未命名')
  const [name, setName] = useState(entry?.name ?? '')
  const [links, setLinks] = useState(() => linkRows(entry))
  const [error, setError] = useState(null)
  const [saved, setSaved] = useState(false)
  const [confirming, setConfirming] = useState(false)

  const save = useApiMutation({ method: isNew ? 'POST' : 'PATCH', invalidate: INVALIDATE })
  const remove = useApiMutation({ method: 'DELETE', invalidate: INVALIDATE })
  const busy = save.isPending || remove.isPending

  const edit = (setter) => (value) => {
    setter(value)
    setSaved(false)
  }

  async function submit() {
    const body = payloadOf(name, links)
    if (body.name === null && body.links.length === 0) {
      setError(new Error(NEEDS_CONTENT))
      return
    }
    setError(null)
    try {
      await save.mutateAsync({
        url: isNew ? endpoints.tbd.create() : endpoints.tbd.update(entry.id),
        body,
      })
      if (isNew) onCreated()
      else setSaved(true)
    } catch (caught) {
      setError(caught)
    }
  }

  async function confirmDelete() {
    try {
      await remove.mutateAsync({ url: endpoints.tbd.remove(entry.id) })
    } catch (caught) {
      setConfirming(false)
      setError(caught)
    }
  }

  const Item = isNew ? 'li' : SortableItem
  const itemProps = isNew ? {} : { id: entry.id, as: 'li' }

  return (
    <Item {...itemProps} aria-label={label} className="space-y-3 rounded-lg border border-border bg-surface p-3">
      <div className="flex items-end gap-2">
        {isNew ? null : <DragHandle label={`「${label}」`} className="mb-1.5" />}
        <Field label="名稱" className="min-w-0 flex-1">
          <Input
            value={name}
            onChange={(event) => edit(setName)(event.target.value)}
            placeholder="可留空"
          />
        </Field>
      </div>

      <div className="space-y-1">
        <p className="text-sm font-medium text-text-muted">連結</p>
        <RowEditor
          rows={links}
          onChange={edit(setLinks)}
          newRow={() => ({ url: '', label: '' })}
          addLabel="新增連結"
          itemLabel="連結"
        >
          {(row, { number, update }) => (
            <div className="grid gap-2 sm:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
              <Input
                aria-label={`連結 ${number} 網址`}
                value={row.url}
                onChange={(event) => update({ url: event.target.value })}
                placeholder="網址"
                inputMode="url"
              />
              <Input
                aria-label={`連結 ${number} 文字`}
                value={row.label}
                onChange={(event) => update({ label: event.target.value })}
                placeholder="顯示文字（可留空）"
              />
            </div>
          )}
        </RowEditor>
      </div>

      {error ? <ErrorNote error={error} /> : null}

      <div className="flex flex-wrap items-center gap-2">
        <Button kind="primary" size="sm" onClick={submit} disabled={busy}>
          {save.isPending ? '儲存中…' : '儲存'}
        </Button>
        {saved ? <span className="text-xs text-text-faint">已儲存</span> : null}
        {isNew ? (
          <Button size="sm" className="ml-auto" onClick={onDiscard} disabled={busy}>
            取消
          </Button>
        ) : (
          <Button kind="danger" size="sm" className="ml-auto" onClick={() => setConfirming(true)} disabled={busy}>
            刪除
          </Button>
        )}
      </div>

      {confirming ? (
        <ConfirmModal
          title="刪除這一項？"
          confirmLabel="刪除"
          danger
          busy={remove.isPending}
          onConfirm={confirmDelete}
          onCancel={() => setConfirming(false)}
        >
          {entry.name ? `「${entry.name}」和它的連結會一起刪除。` : '這一項和它的連結會一起刪除。'}
        </ConfirmModal>
      ) : null}
    </Item>
  )
}
